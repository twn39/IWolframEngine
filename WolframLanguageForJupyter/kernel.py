import os
import re
import sys
import json
import signal
import asyncio
import socket
import threading
from concurrent.futures import Future
from ipykernel.kernelbase import Kernel
from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language.expression import WLFunction, WLSymbol

class StdinServer(threading.Thread):
    def __init__(self, kernel):
        super().__init__()
        self.kernel = kernel
        self.daemon = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('127.0.0.1', 0))
        self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(5)
        
    def run(self):
        while True:
            try:
                conn, addr = self.server_socket.accept()
                req_data = conn.recv(4096).decode('utf-8')
                if not req_data:
                    conn.close()
                    continue
                
                try:
                    req = json.loads(req_data)
                    prompt = req.get("prompt", "")
                except Exception:
                    prompt = req_data
                
                user_input = self.kernel.request_stdin_from_frontend(prompt)
                
                conn.sendall(user_input.encode('utf-8'))
                conn.close()
            except Exception as e:
                break
                
    def close(self):
        try:
            self.server_socket.close()
        except Exception:
            pass

def clean_wolfram_boxes(text):
    text = re.sub(r'[\uf7c0-\uf7c9]', '', text)
    text = re.sub(r'[\uf3c0-\uf3c9]', '', text)
    
    token_pattern = re.compile(r'\"(?:[^\"\\]|\\.)*\"|[a-zA-Z]+|[\[\]\{\}\,]|[^\"a-zA-Z\[\]\{\}\,]+')
    tokens = token_pattern.findall(text)
    
    def parse_expr(tokens, idx):
        if idx >= len(tokens):
            return "", idx
        token = tokens[idx]
        if token.startswith('"'):
            val = token[1:-1].replace('\\"', '"')
            return val, idx + 1
        elif token in ('RowBox', 'StyleBox', 'SubscriptBox', 'SuperscriptBox', 'FractionBox', 'OverscriptBox', 'UnderscriptBox', 'DisplayForm'):
            if idx + 1 < len(tokens) and tokens[idx + 1] == '[':
                args = []
                curr = idx + 2
                while curr < len(tokens) and tokens[curr] != ']':
                    if tokens[curr] == '{':
                        list_items = []
                        curr += 1
                        first = True
                        while curr < len(tokens) and tokens[curr] != '}':
                            if not first:
                                if tokens[curr] == ',':
                                    curr += 1
                                elif tokens[curr].isspace():
                                    curr += 1
                                    continue
                            else:
                                first = False
                            
                            if curr < len(tokens) and tokens[curr] != '}':
                                item, curr = parse_expr(tokens, curr)
                                list_items.append(item)
                        if curr < len(tokens):
                            curr += 1  # consume }
                        args.append("".join(list_items))
                    elif tokens[curr] == ',':
                        curr += 1
                    elif tokens[curr].isspace():
                        curr += 1
                    else:
                        arg, curr = parse_expr(tokens, curr)
                        args.append(arg)
                if curr < len(tokens):
                    curr += 1  # consume ]
                
                if token == 'StyleBox' and len(args) >= 1:
                    return args[0], curr
                elif token == 'SubscriptBox' and len(args) >= 2:
                    return f"{args[0]}_{args[1]}", curr
                elif token == 'SuperscriptBox' and len(args) >= 2:
                    return f"{args[0]}^{args[1]}", curr
                elif token == 'FractionBox' and len(args) >= 2:
                    return f"({args[0]})/({args[1]})", curr
                elif token == 'DisplayForm' and len(args) >= 1:
                    return args[0], curr
                else:
                    return "".join(args), curr
            return token, idx + 1
        elif token in ('[', ']', '{', '}', ','):
            return token, idx + 1
        else:
            return token, idx + 1

    result = []
    idx = 0
    while idx < len(tokens):
        if tokens[idx].isspace():
            result.append(tokens[idx])
            idx += 1
        else:
            item, idx = parse_expr(tokens, idx)
            result.append(item)
        
    return "".join(result)

def format_wolfram_boxes_html(text):
    text = re.sub(r'[\uf7c0-\uf7c9]', '', text)
    text = re.sub(r'[\uf3c0-\uf3c9]', '', text)
    
    token_pattern = re.compile(r'\"(?:[^\"\\]|\\.)*\"|[a-zA-Z]+|[\[\]\{\}\,]|[^\"a-zA-Z\[\]\{\}\,]+')
    tokens = token_pattern.findall(text)
    
    def parse_expr(tokens, idx):
        if idx >= len(tokens):
            return "", idx
        token = tokens[idx]
        if token.startswith('"'):
            val = token[1:-1].replace('\\"', '"')
            return val, idx + 1
        elif token in ('RowBox', 'StyleBox', 'SubscriptBox', 'SuperscriptBox', 'FractionBox', 'OverscriptBox', 'UnderscriptBox', 'DisplayForm'):
            if idx + 1 < len(tokens) and tokens[idx + 1] == '[':
                args = []
                curr = idx + 2
                while curr < len(tokens) and tokens[curr] != ']':
                    if tokens[curr] == '{':
                        list_items = []
                        curr += 1
                        first = True
                        while curr < len(tokens) and tokens[curr] != '}':
                            if not first:
                                if tokens[curr] == ',':
                                    curr += 1
                                elif tokens[curr].isspace():
                                    curr += 1
                                    continue
                            else:
                                first = False
                            
                            if curr < len(tokens) and tokens[curr] != '}':
                                item, curr = parse_expr(tokens, curr)
                                list_items.append(item)
                        if curr < len(tokens):
                            curr += 1  # consume }
                        args.append("".join(list_items))
                    elif tokens[curr] == ',':
                        curr += 1
                    elif tokens[curr].isspace():
                        curr += 1
                    else:
                        arg, curr = parse_expr(tokens, curr)
                        args.append(arg)
                if curr < len(tokens):
                    curr += 1  # consume ]
                
                if token == 'StyleBox' and len(args) >= 1:
                    if len(args) >= 2 and 'TI' in args[1]:
                        return f"<i>{args[0]}</i>", curr
                    return args[0], curr
                elif token == 'SubscriptBox' and len(args) >= 2:
                    return f"{args[0]}<sub>{args[1]}</sub>", curr
                elif token == 'SuperscriptBox' and len(args) >= 2:
                    return f"{args[0]}<sup>{args[1]}</sup>", curr
                elif token == 'FractionBox' and len(args) >= 2:
                    return f'<span style="display:inline-block; vertical-align:middle; text-align:center;"><span style="display:block; border-bottom:1px solid; padding:0 2px;">{args[0]}</span><span style="display:block; padding:0 2px;">{args[1]}</span></span>', curr
                elif token == 'DisplayForm' and len(args) >= 1:
                    return args[0], curr
                else:
                    return "".join(args), curr
            return token, idx + 1
        elif token in ('[', ']', '{', '}', ','):
            return token, idx + 1
        else:
            return token, idx + 1

    result = []
    idx = 0
    while idx < len(tokens):
        if tokens[idx].isspace():
            result.append(tokens[idx])
            idx += 1
        else:
            item, idx = parse_expr(tokens, idx)
            result.append(item)
        
    return "".join(result)

def find_wolfram_kernel():
    path = os.environ.get("WOLFRAM_KERNEL_PATH")
    if path and os.path.exists(path):
        return path
    
    if sys.platform == "darwin":
        mac_paths = [
            "/Applications/Wolfram Engine.app/Contents/Resources/Wolfram Player.app/Contents/MacOS/WolframKernel",
            "/Applications/Mathematica.app/Contents/MacOS/WolframKernel",
            "/Applications/Wolfram Desktop.app/Contents/MacOS/WolframKernel",
        ]
        for p in mac_paths:
            if os.path.exists(p):
                return p
                
    try:
        from wolframclient.evaluation.kernel.path import find_default_kernel_path
        return find_default_kernel_path()
    except ImportError:
        return None

class WolframLanguageKernel(Kernel):
    implementation = 'wolfram_language'
    implementation_version = '1.0.0'
    language = 'wolfram'
    language_version = '1.0.0'
    language_info = {
        'name': 'wolfram',
        'mimetype': 'text/x-wolfram',
        'file_extension': '.wl',
        'pygments_lexer': 'mathematica',
        'codemirror_mode': 'mathematica',
    }
    banner = 'Wolfram Language Kernel'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not getattr(self, "log", None):
            import logging
            self.log = logging.getLogger("WolframLanguageKernel")
            
        # Initialize comms infrastructure for widgets support
        import comm
        import ipykernel.ipkernel
        self.comm_manager = comm.get_comm_manager()
        comm_msg_types = ["comm_open", "comm_msg", "comm_close"]
        for msg_type in comm_msg_types:
            self.shell_handlers[msg_type] = getattr(self.comm_manager, msg_type)

        self.wl_session = None
        self.main_loop = asyncio.get_event_loop()
        self.stdin_server = StdinServer(self)
        self.stdin_server.start()
        
        self._executing = False
        self._interrupted = False
        # 标记是否需要在中断后强制重启（soft interrupt 失败时才置 True）
        self._interrupt_needs_restart = False
        
        self.old_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.handle_sigint)
        
        self.start_wolfram_session()

    # ─── 辅助方法：获取 WolframKernel PID ────────────────────────────────────
    def _get_kernel_pid(self):
        """通过 kernel_controller.pid（公开 API）获取 WolframKernel 进程 PID。"""
        try:
            return self.wl_session.kernel_controller.pid
        except AttributeError:
            return None

    def _is_session_alive(self):
        """检查 WolframKernel 子进程是否仍在运行（poll() == None 表示运行中）。"""
        try:
            return (
                self.wl_session is not None
                and self.wl_session.started
                and self.wl_session.kernel_controller.kernel_proc is not None
                and self.wl_session.kernel_controller.kernel_proc.poll() is None
            )
        except Exception:
            return False

    def _send_soft_interrupt(self):
        """
        向 WolframKernel 进程发送 SIGINT（软中断）。
        WL 收到 SIGINT 后会调用 Abort[]，中止当前计算但保留会话状态。
        返回 True 表示信号发送成功；False 表示失败（需回退到 terminate）。
        """
        pid = self._get_kernel_pid()
        if pid is None:
            return False
        try:
            if sys.platform == "win32":
                import ctypes
                # Windows 需使用 GenerateConsoleCtrlEvent 发送 CTRL_C_EVENT
                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, pid)
            else:
                os.kill(pid, signal.SIGINT)
            self.log.info(f"Sent SIGINT to WolframKernel (PID={pid}) — session preserved.")
            return True
        except (ProcessLookupError, PermissionError, OSError) as e:
            self.log.warning(f"Failed to send SIGINT to PID={pid}: {e}")
            return False

    def handle_sigint(self, signum, frame):
        """SIGINT 处理器：优先尝试软中断（保留会话），失败才回退到 terminate。"""
        self.log.info("SIGINT received in Python kernel.")
        if not getattr(self, "_executing", False):
            # 不在执行中，无需处理
            return

        self._interrupted = True
        soft_ok = self._send_soft_interrupt()
        if not soft_ok:
            # 软中断失败，标记需要在 do_execute 中重启
            self._interrupt_needs_restart = True
            self.log.warning("Soft interrupt failed, will force-restart session after evaluation returns.")
            if self.wl_session:
                try:
                    self.wl_session.terminate()
                except Exception as e:
                    self.log.warning(f"Failed to terminate session in SIGINT handler: {e}")

    def restart_wolfram_session(self):
        self.log.info("Restarting Wolfram Language session...")
        try:
            if self.wl_session:
                self.wl_session.terminate()
        except Exception as e:
            self.log.warning(f"Error terminating session: {e}")
        
        try:
            self.start_wolfram_session()
            self.log.info("Wolfram Language session restarted successfully.")
        except Exception as e:
            self.log.error(f"Failed to restart Wolfram Language session: {e}")

    def _send_interrupt_reply(self, session_restarted: bool):
        """发送中断相关的 IOPub 消息，告知用户会话状态。"""
        if session_restarted:
            note = "Evaluation interrupted by user. The Wolfram session has been restarted. All variables and definitions have been reset."
        else:
            note = "Evaluation interrupted by user. Session state preserved — previously defined variables are still available."
        self.send_response(self.iopub_socket, 'stream', {
            'name': 'stderr',
            'text': f"\n\u26a0\ufe0f  {note}\n"
        })
        self.send_response(self.iopub_socket, 'error', {
            'ename': 'KeyboardInterrupt',
            'evalue': note,
            'traceback': [f'\033[0;31mKeyboardInterrupt: {note}\033[0m']
        })

    def create_manipulate_widget(self, data):
        import ipywidgets as widgets
        import sys
        from wolframclient.language.expression import WLFunction, WLSymbol

        expr_str = data["expression"]
        variables = data["variables"]
        
        controls = {}
        control_list = []
        
        for var in variables:
            name = var["name"]
            var_type = var["type"]
            initial = var["initial"]
            
            if var_type == "Slider":
                is_float = isinstance(var["min"], float) or isinstance(var["max"], float) or isinstance(var["step"], float)
                slider_cls = widgets.FloatSlider if is_float else widgets.IntSlider
                step = var["step"] if var["step"] is not None else (0.1 if is_float else 1)
                
                control = slider_cls(
                    value=initial,
                    min=var["min"],
                    max=var["max"],
                    step=step,
                    description=name,
                    continuous_update=False
                )
            elif var_type == "Dropdown":
                choices = [(choice["label"], choice["value"]) for choice in var["choices"]]
                control = widgets.Dropdown(
                    options=choices,
                    value=initial,
                    description=name
                )
            elif var_type == "Checkbox":
                control = widgets.Checkbox(
                    value=bool(initial),
                    description=name
                )
            else:
                continue
                
            controls[name] = control
            control_list.append(control)
            
        output = widgets.Output()
        
        def update_output(*args):
            bindings = {name: ctrl.value for name, ctrl in controls.items()}
            try:
                func = WLFunction(WLSymbol("WolframLanguageForJupyter`evaluateManipulate"), expr_str, bindings)
                eval_res = self.wl_session.evaluate(func)
                
                new_outputs = []
                if isinstance(eval_res, dict) and eval_res.get("status") == "ok":
                    stdout = eval_res.get("captured_stdout", "")
                    if stdout:
                        new_outputs.append({
                            "output_type": "stream",
                            "name": "stdout",
                            "text": stdout
                        })
                    
                    stderr = eval_res.get("captured_stderr", [])
                    if stderr:
                        new_outputs.append({
                            "output_type": "stream",
                            "name": "stderr",
                            "text": "\n".join(stderr) + "\n"
                        })
                        
                    mime = eval_res.get("mime_bundle", {})
                    if mime:
                        data_dict = mime.get("data", {})
                        metadata_dict = mime.get("metadata", {})
                        new_outputs.append({
                            "output_type": "display_data",
                            "data": data_dict,
                            "metadata": metadata_dict
                        })
                else:
                    new_outputs.append({
                        "output_type": "stream",
                        "name": "stderr",
                        "text": f"Error evaluating Manipulate: {eval_res}\n"
                    })
                output.outputs = tuple(new_outputs)
            except Exception as e:
                output.outputs = ({
                    "output_type": "stream",
                    "name": "stderr",
                    "text": f"Error in update_output: {e}\n"
                },)
                    
        for ctrl in control_list:
            ctrl.observe(update_output, names='value')
            
        update_output()
        
        controls_layout = widgets.VBox(control_list)
        widget_box = widgets.VBox([controls_layout, output])
        return widget_box


    def request_stdin_from_frontend(self, prompt):
        if not getattr(self, "_allow_stdin", False):
            return "$Failed"
            
        future = Future()
        
        def run_in_main_thread():
            try:
                if hasattr(self, "_current_context") and self._current_context:
                    res = self._current_context.run(self.raw_input, prompt)
                else:
                    res = self.raw_input(prompt)
                future.set_result(res)
            except Exception as e:
                future.set_exception(e)
                
        self.main_loop.call_soon_threadsafe(run_in_main_thread)
        try:
            return future.result()
        except Exception:
            return "$Failed"

    def start_wolfram_session(self):
        kernel_path = find_wolfram_kernel()
        if not kernel_path:
            self.log.error("Could not find a valid Wolfram Kernel path. Please set WOLFRAM_KERNEL_PATH.")
            raise RuntimeError("Wolfram Kernel not found.")
        
        self.log.info(f"Starting Wolfram Language session with kernel: {kernel_path}")
        self.wl_session = WolframLanguageSession(kernel_path)
        self.wl_session.start()
        
        # Configure stdin TCP port in WL Private context
        self.wl_session.evaluate(f"WolframLanguageForJupyter`Private`$stdinPort = {self.stdin_server.port};")
        
        try:
            ver = self.wl_session.evaluate('$Version')
            self.language_version = str(ver)
            self.log.info(f"Wolfram Engine Version: {ver}")
        except Exception as e:
            self.log.warning(f"Failed to query Wolfram version: {e}")

        # Load WL resource files inside the WolframLanguageForJupyter context package
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resources_dir = os.path.join(current_dir, "Resources")
        
        # We start the package context block in WL
        self.wl_session.evaluate('BeginPackage["WolframLanguageForJupyter`"]')
        
        files_to_load = [
            "Initialization.wl",
            "OutputHandlingUtilities.wl",
            "EvaluationUtilities.wl",
            "CompletionUtilities.wl"
        ]
        
        for f in files_to_load:
            wl_file = os.path.join(resources_dir, f)
            wl_path_escaped = wl_file.replace("\\", "\\\\")
            self.log.info(f"Loading Wolfram resource file: {wl_file}")
            res = self.wl_session.evaluate(f'Get["{wl_path_escaped}"]')
            if res is not None and ('$Failed' in str(res) or 'Failure' in str(res)):
                self.log.error(f"Failed to load resource: {wl_file}")
                
        # Close the package context block in WL
        self.wl_session.evaluate('EndPackage[]')

    async def _evaluate_user_expressions(self, user_expressions):
        """
        Fix 3: 求值前端传入的 user_expressions。
        每个表达式独立静默求值（不影响 In[]/Out[]，不产生 IOPub 输出）。
        返回符合 Jupyter 协议的 dict：{key: {status, data, metadata} 或 {status, ename, ...}}。
        """
        if not user_expressions:
            return {}
        results = {}
        for key, expr_str in user_expressions.items():
            try:
                # 使用 Module + Quiet 静默求值，不改变 $Line / In / Out
                wl_eval_code = (
                    f'Module[{{$result}}, '
                    f'$result = Quiet[ToExpression["{expr_str.replace(chr(34), chr(92)+chr(34))}", InputForm]]; '
                    f'If[FailureQ[$result] || $result === $Failed, '
                    f'  Association["status" -> "error", "ename" -> "EvaluationError", '
                    f'              "evalue" -> ToString[$result, OutputForm], "traceback" -> {{}}], '
                    f'  Association["status" -> "ok", '
                    f'              "data" -> Association["text/plain" -> ToString[$result, OutputForm]], '
                    f'              "metadata" -> Association[]]]]'
                )
                ue_res = await self.main_loop.run_in_executor(
                    None, lambda c=wl_eval_code: self.wl_session.evaluate(c)
                )
                if isinstance(ue_res, dict):
                    results[key] = ue_res
                else:
                    results[key] = {
                        'status': 'ok',
                        'data': {'text/plain': str(ue_res)},
                        'metadata': {}
                    }
            except Exception as e:
                results[key] = {
                    'status': 'error',
                    'ename': type(e).__name__,
                    'evalue': str(e),
                    'traceback': []
                }
        return results

    async def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
            }
            
        self.main_loop = asyncio.get_running_loop()
        self._allow_stdin = allow_stdin
        import contextvars
        self._current_context = contextvars.copy_context()
        self._executing = True
        self._interrupted = False
        try:
            # Fix 4: 传递 Python 端的 execution_count，使 In[n]/Out[n] 与前端保持同步
            func = WLFunction(
                WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"),
                code,
                self.execution_count
            )
            res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(func))

            # 中断后 WL 可能返回 $Aborted（非 dict），此处检查必须在 isinstance 之前
            if getattr(self, "_interrupted", False):
                # 交由下方 except 块统一处理（即使没有异常抛出）
                raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
            
            if not isinstance(res, dict):
                # Fallback in case evaluation returned something unexpected
                return {
                    'status': 'error',
                    'ename': 'TypeError',
                    'evalue': f'Unexpected return type from evaluator: {type(res)}',
                    'traceback': [str(res)]
                }
                
            stdout_str = res.get("captured_stdout", "")
            if stdout_str:
                self.send_response(self.iopub_socket, 'stream', {'name': 'stdout', 'text': stdout_str})

            stderr_list = res.get("captured_stderr", [])
            if stderr_list:
                stderr_str = "\n".join(str(msg) for msg in stderr_list) + "\n"
                self.send_response(self.iopub_socket, 'stream', {'name': 'stderr', 'text': stderr_str})

            if res.get("status") == "error":
                ename = res.get("ename", "Error")
                evalue = res.get("evalue", "")
                traceback = res.get("traceback", [])
                
                self.send_response(self.iopub_socket, 'error', {
                    'ename': ename,
                    'evalue': evalue,
                    'traceback': list(traceback)
                })
                return {
                    'status': 'error',
                    'ename': ename,
                    'evalue': evalue,
                    'traceback': list(traceback)
                }

            # Fix 2: 处理 mime_bundles 列表
            # 第 1 个 bundle → execute_result（带 execution_count 提示符编号）
            # 后续 bundles → display_data（无编号，视为执行副作用）
            mime_bundles = res.get("mime_bundles", [])
            exec_count = res.get("execution_count", self.execution_count)
            
            if not silent:
                for i, bundle in enumerate(mime_bundles):
                    data = bundle.get("data", {})
                    metadata = bundle.get("metadata", {})
                    
                    # Manipulate 控件处理（保持原有逻辑，每个 bundle 独立检查）
                    if "application/x-wolfram-manipulate" in data:
                        try:
                            widget_box = self.create_manipulate_widget(
                                data["application/x-wolfram-manipulate"]
                            )
                            data = {
                                "application/vnd.jupyter.widget-view+json": {
                                    "version_major": 2,
                                    "version_minor": 0,
                                    "model_id": widget_box.model_id
                                },
                                "text/plain": repr(widget_box)
                            }
                            metadata = {}
                        except Exception as w_err:
                            self.log.error(f"Error creating manipulate widget: {w_err}")
                    
                    if i == 0:
                        # 第一个结果：execute_result（符合 Jupyter 协议：带 [n] 提示符）
                        self.send_response(self.iopub_socket, 'execute_result', {
                            'execution_count': exec_count,
                            'data': data,
                            'metadata': metadata
                        })
                    else:
                        # 后续结果：display_data（无编号，视为副作用输出）
                        self.send_response(self.iopub_socket, 'display_data', {
                            'data': data,
                            'metadata': metadata,
                            'transient': {}
                        })

            # Fix 3: 求值 user_expressions（前端可能用于变量监视等）
            evaluated_user_expr = {}
            if user_expressions and res.get("status") == "ok":
                evaluated_user_expr = await self._evaluate_user_expressions(user_expressions)

            return {
                'status': 'ok',
                'execution_count': exec_count,
                'payload': [],
                'user_expressions': evaluated_user_expr,
            }

        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as e:
            if getattr(self, "_interrupted", False):
                self._interrupted = False
                needs_restart = getattr(self, "_interrupt_needs_restart", False)
                self._interrupt_needs_restart = False

                # 软中断成功时：会话仍然活着，无需重启
                if not needs_restart and self._is_session_alive():
                    session_restarted = False
                    self.log.info("Interrupt handled via SIGINT — Wolfram session preserved.")
                else:
                    # 软中断失败 或 会话已死：重启
                    session_restarted = True
                    self.log.info("Restarting Wolfram session after failed soft interrupt.")
                    self.restart_wolfram_session()

                self._send_interrupt_reply(session_restarted)
                note = (
                    "Evaluation interrupted by user. The Wolfram session has been restarted. All variables and definitions have been reset."
                    if session_restarted
                    else "Evaluation interrupted by user. Session state preserved — previously defined variables are still available."
                )
                return {
                    'status': 'error',
                    'ename': 'KeyboardInterrupt',
                    'evalue': note,
                    'traceback': [f'KeyboardInterrupt: {note}'],
                    'execution_count': self.execution_count,
                }
            
            # Self-healing: if session is dead, restart it
            self.log.error(f"Execution error: {e}")
            is_dead = "not running" in str(e) or not (self.wl_session and self.wl_session.started)
            if is_dead:
                self.restart_wolfram_session()
                
            return {
                'status': 'error',
                'ename': type(e).__name__,
                'evalue': str(e),
                'traceback': [str(e)]
            }
        finally:
            self._executing = False
            self._interrupted = False
            self._interrupt_needs_restart = False

    def do_complete(self, code, cursor_pos):
        prefix = code[:cursor_pos]
        try:
            func = WLFunction(WLSymbol("WolframLanguageForJupyter`getCompletions"), prefix)
            res = self.wl_session.evaluate(func)
            if isinstance(res, dict):
                return {
                    'status': 'ok',
                    'matches': list(res.get("matches", [])),
                    'cursor_start': int(res.get("cursor_start", cursor_pos)),
                    'cursor_end': int(res.get("cursor_end", cursor_pos)),
                    'metadata': {}
                }
        except Exception as e:
            self.log.error(f"Error in autocomplete: {e}")
            
        return {
            'status': 'ok',
            'matches': [],
            'cursor_start': cursor_pos,
            'cursor_end': cursor_pos,
            'metadata': {}
        }

    def do_inspect(self, code, cursor_pos, detail_level=0, *args, **kwargs):
        pattern = re.compile(r'[a-zA-Z\$`][a-zA-Z0-9\$`]*')
        symbol = None
        for match in pattern.finditer(code):
            if match.start() <= cursor_pos <= match.end():
                symbol = match.group(0)
                break
                
        if not symbol:
            return {'status': 'ok', 'found': False, 'data': {}, 'metadata': {}}
            
        try:
            # Query structured symbol documentation via a single evaluation block
            wl_code = f"""
            Module[{{sym, usage, doc, options, docLink}},
                If[!NameQ["{symbol}"] && !NameQ["System`{symbol}"],
                    Return[Association["found" -> False]]
                ];
                sym = Symbol[If[NameQ["{symbol}"], "{symbol}", "System`{symbol}"]];
                options = Information[sym, "Options"];
                If[FailureQ[options], options = None];
                doc = Information[sym, "Documentation"];
                docLink = If[AssociationQ[doc], Lookup[doc, "Web", ""], ""];
                usage = Information[sym, "Usage"];
                If[FailureQ[usage] || !StringQ[ToString[usage]], usage = ""];
                If[StringQ[usage] && usage =!= "", usage = ToString[InputForm[usage]]];
                Association[
                    "found" -> True,
                    "usage" -> usage,
                    "docLink" -> ToString[docLink],
                    "options" -> ToString[InputForm[options]]
                ]
            ]
            """
            res = self.wl_session.evaluate(wl_code)
            
            if isinstance(res, dict) and res.get("found"):
                raw_usage = res.get("usage", "")
                doc_link = res.get("docLink", "")
                options_str = res.get("options", "")
                
                # Check for empty usage fallback
                if not raw_usage:
                    try:
                        fallback_expr = WLFunction(
                            WLSymbol("ToString"),
                            WLFunction(
                                WLSymbol("InputForm"),
                                WLFunction(
                                    WLSymbol("MessageName"),
                                    WLFunction(WLSymbol("Evaluate"), WLFunction(WLSymbol("Symbol"), symbol)),
                                    "usage"
                                )
                            )
                        )
                        fallback_usage = self.wl_session.evaluate(fallback_expr)
                        if isinstance(fallback_usage, str) and not fallback_usage.endswith("::usage") and fallback_usage != "$Failed":
                            raw_usage = fallback_usage
                    except Exception:
                        pass

                if not raw_usage:
                    raw_usage = f"Symbol: {symbol}"

                # Parse and clean box structures
                # Strip outer quotes if they exist (since InputForm wraps the string in quotes)
                if raw_usage.startswith('"') and raw_usage.endswith('"'):
                    raw_usage = raw_usage[1:-1]
                # Unescape backslashes and newlines
                raw_usage = raw_usage.replace('\\\\', '\\').replace('\\n', '\n')
                # Convert Wolfram string box brackets to DisplayForm / brackets, and unescape quotes
                processed_usage = raw_usage.replace(r"\!\(\*", "DisplayForm[").replace(r"\)", "]").replace(r'\"', '"')
                cleaned_usage = clean_wolfram_boxes(processed_usage)
                html_usage = format_wolfram_boxes_html(processed_usage)
                
                # Create HTML layout styled for Jupyter Lab (light/dark theme variables)
                html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; line-height: 1.5; color: var(--jp-content-font-color1, #333); max-width: 600px;">
    <h3 style="margin-top: 0; margin-bottom: 8px; font-size: 15px; font-weight: bold; border-bottom: 1px solid var(--jp-border-color1, #e0e0e0); padding-bottom: 4px;">
        <span style="color: #d9534f;">{symbol}</span>
    </h3>
    <div style="margin-bottom: 12px; white-space: pre-wrap;">{html_usage}</div>
"""
                if options_str and options_str != "None" and options_str != "Null":
                    opts = options_str.strip()
                    if opts.startswith("{") and opts.endswith("}"):
                        opts = opts[1:-1]
                    html += f"""
    <div style="margin-bottom: 12px;">
        <strong style="color: var(--jp-content-font-color2, #666); font-size: 12px;">Options:</strong>
        <pre style="margin: 4px 0 0 0; padding: 6px; background-color: var(--jp-layout-color2, #f5f5f5); border: 1px solid var(--jp-border-color2, #e0e0e0); border-radius: 4px; font-family: monospace; font-size: 11px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">{opts}</pre>
    </div>
"""
                if doc_link:
                    html += f"""
    <div style="text-align: right; font-size: 11px; margin-top: 8px;">
        <a href="{doc_link}" target="_blank" style="color: #0275d8; text-decoration: none; font-weight: 500;">
            Online Reference &#x2197;
        </a>
    </div>
"""
                html += "</div>"
                
                # Create Markdown layout
                markdown = f"### `{symbol}`\n\n{cleaned_usage}\n\n"
                if options_str and options_str != "None" and options_str != "Null":
                    opts = options_str.strip()
                    if opts.startswith("{") and opts.endswith("}"):
                        opts = opts[1:-1]
                    markdown += f"**Options:**\n```wolfram\n{opts}\n```\n\n"
                if doc_link:
                    markdown += f"[Online Reference]({doc_link})\n"
                
                return {
                    'status': 'ok',
                    'found': True,
                    'data': {
                        'text/plain': cleaned_usage,
                        'text/markdown': markdown,
                        'text/html': html
                    },
                    'metadata': {}
                }
        except Exception as e:
            self.log.error(f"Error in do_inspect: {e}")
            
        return {'status': 'ok', 'found': False, 'data': {}, 'metadata': {}}

    def _check_completeness(self, code: str) -> tuple[str, str]:
        """
        本地分析器：分析 Wolfram 代码是否语法完整。
        返回 (status, indent)，其中 status 为 'complete'、'incomplete' 或 'invalid'。
        """
        stack = []
        in_string = False
        comment_depth = 0
        i = 0
        n = len(code)
        
        last_non_ws_char = None
        last_non_ws_index = -1
        
        while i < n:
            if in_string:
                if code[i:i+2] == '\\"' or code[i:i+2] == '\\\\':
                    i += 2
                elif code[i] == '"':
                    in_string = False
                    i += 1
                else:
                    i += 1
            elif comment_depth > 0:
                if code[i:i+2] == '(*':
                    comment_depth += 1
                    i += 2
                elif code[i:i+2] == '*)':
                    comment_depth -= 1
                    i += 2
                else:
                    i += 1
            else:
                char = code[i]
                if char == '"':
                    in_string = True
                    last_non_ws_char = '"'
                    last_non_ws_index = i
                    i += 1
                elif code[i:i+2] == '(*':
                    comment_depth = 1
                    i += 2
                elif code[i:i+2] == '<|':
                    stack.append('<|')
                    last_non_ws_char = '|'
                    last_non_ws_index = i + 1
                    i += 2
                elif code[i:i+2] == '|>':
                    if stack and stack[-1] == '<|':
                        stack.pop()
                        last_non_ws_char = '>'
                        last_non_ws_index = i + 1
                        i += 2
                    else:
                        return 'invalid', ''
                elif char in '([{':
                    stack.append(char)
                    last_non_ws_char = char
                    last_non_ws_index = i
                    i += 1
                elif char in ')]}':
                    if not stack:
                        return 'invalid', ''
                    opening = stack.pop()
                    if (char == ')' and opening != '(') or \
                       (char == ']' and opening != '[') or \
                       (char == '}' and opening != '{'):
                        return 'invalid', ''
                    last_non_ws_char = char
                    last_non_ws_index = i
                    i += 1
                else:
                    if not char.isspace():
                        last_non_ws_char = char
                        last_non_ws_index = i
                    i += 1
                    
        if in_string or comment_depth > 0 or stack:
            # 每一层未闭合的括号增加 4 个空格缩进
            indent_level = len(stack)
            if in_string or comment_depth > 0:
                indent_level += 1
            return 'incomplete', '    ' * indent_level

        if last_non_ws_char is not None:
            # 若以续行符/操作符结尾，则属于 incomplete
            if last_non_ws_char in '+-*/^=><,@~:|':
                if last_non_ws_char == '>':
                    # 区分 |> (结合闭合) 和 纯大于号/规则符号 (->, :>, >)
                    if last_non_ws_index > 0 and code[last_non_ws_index - 1] == '|':
                        pass
                    else:
                        return 'incomplete', '    '
                else:
                    return 'incomplete', '    '
            
            # && 逻辑与结尾
            if last_non_ws_char == '&':
                if last_non_ws_index > 0 and code[last_non_ws_index - 1] == '&':
                    return 'incomplete', '    '
                
            # . 点号结尾（排除类似 3. 的浮点数）
            if last_non_ws_char == '.':
                if last_non_ws_index > 0 and code[last_non_ws_index - 1].isdigit():
                    pass
                else:
                    return 'incomplete', '    '

        return 'complete', ''

    def do_is_complete(self, code: str) -> dict:
        """
        Jupyter protocol: 检查代码输入是否完整。
        """
        try:
            status, indent = self._check_completeness(code)
            reply = {'status': status}
            if status == 'incomplete':
                reply['indent'] = indent
            return reply
        except Exception as e:
            self.log.error(f"Error in do_is_complete: {e}")
            return {'status': 'unknown'}

    def do_shutdown(self, restart):
        if hasattr(self, "stdin_server") and self.stdin_server:
            self.stdin_server.close()
        if self.wl_session:
            try:
                self.wl_session.terminate()
            except Exception as e:
                self.log.warning(f"Error terminating Wolfram session: {e}")
        return super().do_shutdown(restart)

if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=WolframLanguageKernel)
