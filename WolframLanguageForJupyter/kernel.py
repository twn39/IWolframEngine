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
        var_types = {}
        
        for var in variables:
            name = var["name"]
            var_type = var["type"]
            initial = var["initial"]
            var_types[name] = var_type
            
            if var_type == "Slider":
                is_float = isinstance(var.get("min", 0), float) or isinstance(var.get("max", 1), float) or isinstance(var.get("step", 0.1), float)
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
            elif var_type == "Dropdown" or var_type == "PopupMenu":
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
            elif var_type == "RadioButton":
                choices = [(choice["label"], choice["value"]) for choice in var["choices"]]
                control = widgets.RadioButtons(
                    options=choices,
                    value=initial,
                    description=name
                )
            elif var_type == "SetterBar":
                choices = [(choice["label"], choice["value"]) for choice in var["choices"]]
                control = widgets.ToggleButtons(
                    options=choices,
                    value=initial,
                    description=name
                )
            elif var_type == "InputField":
                control = widgets.Text(
                    value=str(initial) if initial is not None else "",
                    description=name,
                    continuous_update=False
                )
            elif var_type == "Trigger":
                is_float = isinstance(var.get("min", 0), float) or isinstance(var.get("max", 1), float) or isinstance(var.get("step", 0.1), float)
                slider_cls = widgets.FloatSlider if is_float else widgets.IntSlider
                step = var["step"] if var["step"] is not None else (0.1 if is_float else 1)
                
                slider = slider_cls(
                    value=initial,
                    min=var["min"],
                    max=var["max"],
                    step=step,
                    description=name,
                    continuous_update=False
                )
                
                play = widgets.Play(
                    value=0,
                    min=0,
                    max=100,
                    step=1,
                    interval=100
                )
                
                # Bidirectional observers
                def make_play_observer(s_ctrl, v_min, v_max):
                    def on_play_change(change):
                        pct = change['new'] / 100.0
                        s_ctrl.value = v_min + pct * (v_max - v_min)
                    return on_play_change
                    
                play.observe(make_play_observer(slider, var["min"], var["max"]), names='value')
                
                def make_slider_observer(p_ctrl, v_min, v_max):
                    def on_slider_change(change):
                        val = change['new']
                        if v_max != v_min:
                            pct = (val - v_min) / (v_max - v_min)
                            p_ctrl.value = int(pct * 100)
                    return on_slider_change
                    
                slider.observe(make_slider_observer(play, var["min"], var["max"]), names='value')
                
                control = widgets.HBox([play, slider])
            elif var_type == "Locator":
                init_x = 0.0
                init_y = 0.0
                if isinstance(initial, list) and len(initial) == 2:
                    init_x = float(initial[0])
                    init_y = float(initial[1])
                
                x_slider = widgets.FloatSlider(value=init_x, min=-1.0, max=1.0, step=0.01, description=f"{name}_x", continuous_update=False)
                y_slider = widgets.FloatSlider(value=init_y, min=-1.0, max=1.0, step=0.01, description=f"{name}_y", continuous_update=False)
                control = widgets.VBox([x_slider, y_slider])
            else:
                continue
                
            controls[name] = control
            control_list.append(control)
            
        stdout_area = widgets.HTML(value="")
        stderr_area = widgets.HTML(value="")
        display_area = widgets.HTML(value="")
        output_box = widgets.VBox([stdout_area, stderr_area, display_area])
        
        def get_val(ctrl, var_type):
            if var_type == "Trigger":
                return ctrl.children[1].value
            elif var_type == "Locator":
                return [ctrl.children[0].value, ctrl.children[1].value]
            else:
                return ctrl.value
        
        def update_output(*args):
            bindings = {name: get_val(ctrl, var_types[name]) for name, ctrl in controls.items()}
            try:
                func = WLFunction(WLSymbol("WolframLanguageForJupyter`evaluateManipulate"), expr_str, bindings)
                eval_res = self.wl_session.evaluate(func)
                
                if isinstance(eval_res, dict) and eval_res.get("status") == "ok":
                    stdout = eval_res.get("captured_stdout", "")
                    if stdout:
                        stdout_area.value = f"<pre style='margin: 0; font-family: monospace;'>{stdout}</pre>"
                        stdout_area.layout.display = 'block'
                    else:
                        stdout_area.value = ""
                        stdout_area.layout.display = 'none'
                    
                    stderr = eval_res.get("captured_stderr", [])
                    if stderr:
                        stderr_text = "\n".join(stderr)
                        stderr_area.value = f"<pre style='margin: 0; font-family: monospace; color: red;'>{stderr_text}</pre>"
                        stderr_area.layout.display = 'block'
                    else:
                        stderr_area.value = ""
                        stderr_area.layout.display = 'none'
                        
                    mime = eval_res.get("mime_bundle", {})
                    if mime:
                        data_dict = mime.get("data", {})
                        metadata_dict = mime.get("metadata", {})
                        
                        if "image/svg+xml" in data_dict:
                            import uuid
                            unique_id = str(uuid.uuid4().hex)[:8]
                            display_area.value = data_dict["image/svg+xml"].replace("glyph", f"glyph_{unique_id}").replace("clip", f"clip_{unique_id}")
                        elif "image/png" in data_dict:
                            png_base64 = data_dict["image/png"]
                            png_meta = metadata_dict.get("image/png", {})
                            width = png_meta.get("width")
                            height = png_meta.get("height")
                            
                            style_str = ""
                            if width and height:
                                style_str = f"width: {width}px; height: {height}px;"
                            elif width:
                                style_str = f"width: {width}px;"
                            
                            display_area.value = f'<img src="data:image/png;base64,{png_base64}" style="{style_str}" />'
                        elif "text/html" in data_dict:
                            display_area.value = data_dict["text/html"]
                        elif "text/plain" in data_dict:
                            display_area.value = f"<pre style='margin: 0; font-family: monospace;'>{data_dict['text/plain']}</pre>"
                        else:
                            display_area.value = ""
                    else:
                        display_area.value = ""
                else:
                    err_msg = f"Error evaluating Manipulate: {eval_res}"
                    stderr_area.value = f"<pre style='margin: 0; font-family: monospace; color: red;'>{err_msg}</pre>"
                    stderr_area.layout.display = 'block'
                    display_area.value = ""
            except Exception as e:
                err_msg = f"Error in update_output: {e}"
                stderr_area.value = f"<pre style='margin: 0; font-family: monospace; color: red;'>{err_msg}</pre>"
                stderr_area.layout.display = 'block'
                    
        for name, ctrl in controls.items():
            var_type = var_types[name]
            if var_type == "Trigger":
                ctrl.children[1].observe(update_output, names='value')
            elif var_type == "Locator":
                ctrl.children[0].observe(update_output, names='value')
                ctrl.children[1].observe(update_output, names='value')
            else:
                ctrl.observe(update_output, names='value')
            
        update_output()
        
        controls_layout = widgets.VBox(control_list)
        widget_box = widgets.VBox([controls_layout, output_box])
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

    def _parse_execution_segments(self, code: str) -> list[dict]:
        lines = code.splitlines(keepends=True)
        if not lines:
            return []
            
        first_non_empty_idx = -1
        for idx, line in enumerate(lines):
            if line.strip():
                first_non_empty_idx = idx
                break
                
        if first_non_empty_idx != -1:
            first_line_stripped = lines[first_non_empty_idx].strip()
            if first_line_stripped.startswith("%%sh"):
                cell_code = "".join(lines[first_non_empty_idx+1:])
                return [{'type': 'sh', 'content': cell_code}]
            elif first_line_stripped.startswith("%%timeit"):
                prefix_idx = lines[first_non_empty_idx].find("%%timeit")
                args = lines[first_non_empty_idx][prefix_idx + 8:].strip()
                cell_code = "".join(lines[first_non_empty_idx+1:])
                return [{'type': 'timeit', 'magic_type': 'cell', 'args': args, 'content': cell_code}]
            elif first_line_stripped.startswith("%%time"):
                cell_code = "".join(lines[first_non_empty_idx+1:])
                return [{'type': 'time', 'magic_type': 'cell', 'content': cell_code}]
            
        segments = []
        current_wolfram = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("%%sh"):
                # If they write cell magic in the middle of cell (unusual but supported), treat remaining as shell
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                prefix_idx = line.find("%%sh")
                cell_code = line[prefix_idx + 4:] + "".join(lines[lines.index(line)+1:])
                segments.append({'type': 'sh', 'content': cell_code})
                break
            elif stripped.startswith("%sh") and (len(stripped) == 3 or stripped[3].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                prefix_idx = line.find("%sh")
                cmd = line[prefix_idx + 3:].strip()
                segments.append({'type': 'sh', 'content': cmd})
            elif stripped.startswith("%workspace") and (len(stripped) == 10 or stripped[10].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                segments.append({'type': 'workspace'})
            elif stripped.startswith("%clear") and (len(stripped) == 6 or stripped[6].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                segments.append({'type': 'clear'})
            elif stripped.startswith("%session") and (len(stripped) == 8 or stripped[8].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                prefix_idx = line.find("%session")
                action = line[prefix_idx + 8:].strip().lower() or "info"
                segments.append({'type': 'session', 'action': action})
            elif stripped.startswith("%timeit") and (len(stripped) == 7 or stripped[7].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                prefix_idx = line.find("%timeit")
                args_and_code = line[prefix_idx + 7:].strip()
                segments.append({'type': 'timeit', 'magic_type': 'line', 'args_and_code': args_and_code})
            elif stripped.startswith("%time") and (len(stripped) == 5 or stripped[5].isspace()):
                if current_wolfram:
                    segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
                    current_wolfram = []
                prefix_idx = line.find("%time")
                cmd = line[prefix_idx + 5:].strip()
                segments.append({'type': 'time', 'magic_type': 'line', 'content': cmd})
            else:
                current_wolfram.append(line)
                
        if current_wolfram:
            segments.append({'type': 'wolfram', 'content': "".join(current_wolfram)})
            
        return segments

    async def _run_shell_command(self, cmd_line: str, silent: bool) -> dict:
        if not cmd_line.strip():
            return {'status': 'ok'}
            
        try:
            process = await asyncio.create_subprocess_shell(
                cmd_line,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            async def read_stream(stream, name):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='replace')
                    if not silent:
                        self.send_response(self.iopub_socket, 'stream', {
                            'name': name,
                            'text': decoded_line
                        })
            
            await asyncio.gather(
                read_stream(process.stdout, 'stdout'),
                read_stream(process.stderr, 'stderr')
            )
            
            returncode = await process.wait()
            if returncode != 0:
                if not silent:
                    self.send_response(self.iopub_socket, 'stream', {
                        'name': 'stderr',
                        'text': f"\nShell command failed with exit code {returncode}\n"
                    })
                return {
                    'status': 'error',
                    'ename': 'ShellError',
                    'evalue': f'Exit code {returncode}',
                    'traceback': [f"Exit code {returncode}"]
                }
            return {'status': 'ok'}
        except Exception as e:
            if not silent:
                self.send_response(self.iopub_socket, 'stream', {
                    'name': 'stderr',
                    'text': f"Error executing shell command: {e}\n"
                })
            return {
                'status': 'error',
                'ename': type(e).__name__,
                'evalue': str(e),
                'traceback': [str(e)]
            }

    def _format_workspace_report(self, var_list: list) -> dict:
        if not var_list:
            html = '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; padding: 10px; color: var(--jp-content-font-color2, #666);">Workspace is empty (no variables defined in Global` context).</div>'
            text = "Workspace is empty."
            return {'text/plain': text, 'text/html': html}
            
        rows = []
        for var in var_list:
            name = var.get("name", "") if isinstance(var, dict) else ""
            v_type = var.get("type", "") if isinstance(var, dict) else ""
            size = var.get("size", 0) if isinstance(var, dict) else 0
            val_prev = var.get("value", "") if isinstance(var, dict) else ""
            
            # If name is a WLSymbol, convert to string
            if hasattr(name, 'name'):
                name = name.name
            if hasattr(v_type, 'name'):
                v_type = v_type.name
                
            name = str(name)
            v_type = str(v_type)
            val_prev = str(val_prev)
            
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
                
            rows.append(f"""
            <tr>
                <td style="font-weight: bold; color: #d9534f;">{name}</td>
                <td style="font-family: monospace; color: #4b86b4;">{v_type}</td>
                <td style="text-align: right; font-family: monospace;">{size_str}</td>
                <td><pre style="margin: 0; white-space: pre-wrap; font-family: monospace; font-size: 12px; background: none; border: none; padding: 0;">{val_prev}</pre></td>
            </tr>
            """)
            
        html = f"""
        <div class="wolfram-workspace-container">
            <style>
                .wolfram-workspace-container {{ overflow-x: auto; margin: 12px 0; }}
                table.wolfram-workspace {{ border-collapse: collapse; font-family: var(--jp-content-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif); font-size: var(--jp-content-font-size1, 14px); color: var(--jp-content-font-color1, black); border: 1px solid var(--jp-border-color1, #dcdcdc); text-align: left; min-width: 600px; background-color: var(--jp-layout-color1, #ffffff); box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 4px; }}
                table.wolfram-workspace th {{ background-color: var(--jp-layout-color2, #f5f5f5); color: var(--jp-content-font-color1, black); font-weight: 600; padding: 8px 12px; border: 1px solid var(--jp-border-color1, #dcdcdc); }}
                table.wolfram-workspace td {{ padding: 8px 12px; border: 1px solid var(--jp-border-color2, #e0e0e0); vertical-align: middle; }}
                table.wolfram-workspace tbody tr:nth-child(even) {{ background-color: var(--jp-layout-color2, #fafafa); }}
                table.wolfram-workspace tbody tr:hover {{ background-color: var(--jp-layout-color3, #f0f0f0); }}
            </style>
            <table class="wolfram-workspace">
                <thead>
                    <tr>
                         <th>Variable</th>
                         <th>Type (Head)</th>
                         <th>Size</th>
                         <th>Value / Definition</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
         </div>
         """
         
        text_rows = []
        for var in var_list:
            var_name = var.get("name", "")
            if hasattr(var_name, 'name'):
                var_name = var_name.name
            var_type = var.get("type", "")
            if hasattr(var_type, 'name'):
                var_type = var_type.name
            text_rows.append(f"{var_name}: Head={var_type}, Size={var.get('size')} Bytes, Value={var.get('value')}")
        text = "Workspace variables:\n" + "\n".join(text_rows)
        
        return {'text/plain': text, 'text/html': html}

    def _get_subprocess_memory(self, pid: int) -> int | None:
        """Get the memory RSS of the process with given PID. Attempts psutil first, then falls back to ps command."""
        if pid is None:
            return None
        try:
            import psutil
            process = psutil.Process(pid)
            return process.memory_info().rss
        except Exception:
            # Fallback for macOS/Linux using ps command
            try:
                import subprocess
                out = subprocess.check_output(["ps", "-p", str(pid), "-o", "rss"]).decode('utf-8', errors='ignore')
                lines = out.strip().splitlines()
                if len(lines) >= 2:
                    rss_kb = int(lines[1].strip())
                    return rss_kb * 1024
            except Exception:
                pass
        return None

    def _format_session_info(self, info: dict) -> dict:
        # Formatted memory
        mem = info.get("memory_bytes")
        if mem is None:
            mem_str = "Unknown"
        elif mem < 1024:
            mem_str = f"{mem} B"
        elif mem < 1024 * 1024:
            mem_str = f"{mem / 1024:.1f} KB"
        elif mem < 1024 * 1024 * 1024:
            mem_str = f"{mem / (1024 * 1024):.1f} MB"
        else:
            mem_str = f"{mem / (1024 * 1024 * 1024):.1f} GB"

        # Formatted context path
        ctx_list = info.get("context_path", [])
        if isinstance(ctx_list, (list, tuple)):
            ctx_str = ", ".join(ctx_list)
        else:
            ctx_str = str(ctx_list)

        rows = [
            ("Wolfram Version", info.get("version", "Unknown")),
            ("License Type", info.get("license_type", "Unknown")),
            ("License ID", info.get("license_id", "Unknown")),
            ("Machine ID", info.get("machine_id", "Unknown")),
            ("System ID", info.get("system_id", "Unknown")),
            ("Context Path", ctx_str),
            ("Process ID (PID)", str(info.get("pid", "Unknown"))),
            ("Memory Usage", mem_str),
            ("Executable Path", info.get("executable_path", "Unknown")),
            ("Stdin Bridge Port", str(info.get("stdin_port", "Unknown"))),
        ]

        html_rows = []
        for label, val in rows:
            html_rows.append(f"""
            <tr>
                <td style="font-weight: 600; color: var(--jp-content-font-color2, #555); width: 180px; padding: 6px 12px; border: 1px solid var(--jp-border-color2, #e0e0e0);">{label}</td>
                <td style="font-family: monospace; color: var(--jp-content-font-color1, #111); padding: 6px 12px; border: 1px solid var(--jp-border-color2, #e0e0e0); white-space: pre-wrap; word-break: break-all;">{val}</td>
            </tr>
            """)

        html = f"""
        <div class="wolfram-session-container" style="margin: 12px 0; font-family: var(--jp-content-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif);">
            <style>
                .wolfram-session-card {{
                    border: 1px solid var(--jp-border-color1, #dcdcdc);
                    border-radius: 6px;
                    background-color: var(--jp-layout-color1, #ffffff);
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                    overflow: hidden;
                    max-width: 800px;
                }}
                .wolfram-session-header {{
                    background-color: var(--jp-layout-color2, #f5f5f5);
                    padding: 10px 16px;
                    border-bottom: 1px solid var(--jp-border-color1, #dcdcdc);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }}
                .wolfram-session-title {{
                    font-weight: bold;
                    font-size: 14px;
                    color: var(--jp-content-font-color1, #333);
                }}
                .wolfram-session-status {{
                    display: inline-flex;
                    align-items: center;
                    font-size: 12px;
                    font-weight: 600;
                    color: #5cb85c;
                }}
                .wolfram-session-status::before {{
                    content: "";
                    display: inline-block;
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background-color: #5cb85c;
                    margin-right: 6px;
                }}
                .wolfram-session-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 13px;
                }}
            </style>
            <div class="wolfram-session-card">
                <div class="wolfram-session-header">
                    <span class="wolfram-session-title">Wolfram Engine Session Information</span>
                    <span class="wolfram-session-status">Active</span>
                </div>
                <table class="wolfram-session-table">
                    <tbody>
                        {"".join(html_rows)}
                    </tbody>
                </table>
            </div>
        </div>
        """

        text_rows = [f"{label}: {val}" for label, val in rows]
        text = "Wolfram Engine Session Information:\n" + "\n".join(text_rows)

        return {'text/plain': text, 'text/html': html}

    def _parse_timeit_args(self, args_str: str) -> tuple[int | None, int, str]:
        """Parse -n <loops> and -r <runs> from timeit command string, returning (loops, runs, code)."""
        import shlex
        try:
            parts = shlex.split(args_str)
        except Exception:
            parts = args_str.split()
            
        loops = None
        runs = 7
        code_parts = []
        
        i = 0
        while i < len(parts):
            if parts[i] == '-n' and i + 1 < len(parts):
                try:
                    loops = int(parts[i+1])
                    i += 2
                    continue
                except ValueError:
                    pass
            elif parts[i] == '-r' and i + 1 < len(parts):
                try:
                    runs = int(parts[i+1])
                    i += 2
                    continue
                except ValueError:
                    pass
            # Everything after the first non-option is the code
            code_parts = parts[i:]
            break
            
        # Extract code preserving original whitespace/newlines from args_str if possible
        code = ""
        if code_parts:
            first_part = code_parts[0]
            idx = args_str.find(first_part)
            if idx != -1:
                code = args_str[idx:]
            else:
                code = " ".join(code_parts)
        else:
            code = args_str.strip()
            
        return loops, runs, code

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
            segments = self._parse_execution_segments(code)
            exec_count = self.execution_count
            execute_result_sent = False
            last_res = None
            wolfram_segment_idx = 0
            
            for segment in segments:
                if getattr(self, "_interrupted", False):
                    raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
                    
                if segment['type'] == 'sh':
                    sh_res = await self._run_shell_command(segment['content'], silent)
                    if sh_res.get("status") == "error":
                        return {
                            'status': 'error',
                            'ename': sh_res.get("ename", "ShellError"),
                            'evalue': sh_res.get("evalue", ""),
                            'traceback': sh_res.get("traceback", []),
                            'execution_count': exec_count
                        }
                elif segment['type'] == 'workspace':
                    wl_query = """
                    Begin["WolframLanguageForJupyter`Private`"];
                    getWorkspace[] := Module[{symNames, syms},
                        symNames = Names["Global`*"];
                        syms = Select[symNames, Function[name,
                            Block[{shortName = StringReplace[name, "Global`" -> ""], heldSym = ToExpression[name, InputForm, Hold]},
                                (!StringStartsQ[shortName, "$"]) &&
                                (!StringStartsQ[shortName, "Private"]) &&
                                (!StringContainsQ[shortName, "$"]) &&
                                (
                                    (OwnValues @@ heldSym) =!= {} ||
                                    (DownValues @@ heldSym) =!= {} ||
                                    (SubValues @@ heldSym) =!= {} ||
                                    (UpValues @@ heldSym) =!= {}
                                )
                            ]
                        ]];
                        Map[Function[name,
                            Block[{sym = Symbol[name], value, type, size, shortVal},
                                type = Head[sym];
                                size = Quiet[ByteCount[sym]];
                                If[FailureQ[size], size = 0];
                                value = sym;
                                shortVal = Quiet[ToString[Short[value, 3], InputForm]];
                                If[FailureQ[shortVal], shortVal = ""];
                                Association[
                                    "name" -> StringReplace[name, "Global`" -> ""],
                                    "type" -> ToString[type],
                                    "size" -> size,
                                    "value" -> shortVal
                                ]
                            ]
                        ], syms]
                    ];
                    res = getWorkspace[];
                    ClearAll[getWorkspace];
                    End[];
                    res
                    """
                    res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(wl_query))
                    if isinstance(res, (list, tuple)):
                        data_bundle = self._format_workspace_report(res)
                    else:
                        data_bundle = self._format_workspace_report([])
                        
                    if not silent:
                        if not execute_result_sent:
                            self.send_response(self.iopub_socket, 'execute_result', {
                                'execution_count': exec_count,
                                'data': data_bundle,
                                'metadata': {}
                            })
                            execute_result_sent = True
                        else:
                            self.send_response(self.iopub_socket, 'display_data', {
                                'data': data_bundle,
                                'metadata': {},
                                'transient': {}
                            })
                elif segment['type'] == 'clear':
                    await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate('ClearAll["Global`*"]'))
                    if not silent:
                        self.send_response(self.iopub_socket, 'stream', {
                            'name': 'stdout',
                            'text': "Cleared all variables in Global` context.\n"
                        })
                elif segment['type'] == 'session':
                    action = segment.get('action', 'info')
                    if action == 'info':
                        wl_query = """
                        Association[
                            "version" -> $Version,
                            "license_type" -> $LicenseType,
                            "license_id" -> $LicenseID,
                            "machine_id" -> $MachineID,
                            "system_id" -> $SystemID,
                            "context_path" -> $ContextPath
                        ]
                        """
                        try:
                            res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(wl_query))
                        except Exception as e:
                            res = None
                            self.log.warning(f"Failed to query session info from Wolfram: {e}")

                        pid = None
                        executable_path = "Unknown"
                        if self.wl_session and getattr(self.wl_session, "kernel_controller", None):
                            pid = self.wl_session.kernel_controller.pid
                        if self.wl_session and getattr(self.wl_session, "kernel", None):
                            executable_path = self.wl_session.kernel

                        mem_bytes = self._get_subprocess_memory(pid) if pid else None

                        info = {
                            "version": "Unknown",
                            "license_type": "Unknown",
                            "license_id": "Unknown",
                            "machine_id": "Unknown",
                            "system_id": "Unknown",
                            "context_path": [],
                            "pid": pid,
                            "memory_bytes": mem_bytes,
                            "executable_path": executable_path,
                            "stdin_port": self.stdin_server.port if getattr(self, "stdin_server", None) else "Unknown"
                        }

                        if isinstance(res, dict):
                            for k, v in res.items():
                                if hasattr(v, 'name'):
                                    v = v.name
                                info[k] = v

                        if "context_path" in info and isinstance(info["context_path"], (list, tuple)):
                            info["context_path"] = [c.name if hasattr(c, 'name') else str(c) for c in info["context_path"]]

                        data_bundle = self._format_session_info(info)

                        if not silent:
                            if not execute_result_sent:
                                self.send_response(self.iopub_socket, 'execute_result', {
                                    'execution_count': exec_count,
                                    'data': data_bundle,
                                    'metadata': {}
                                })
                                execute_result_sent = True
                            else:
                                self.send_response(self.iopub_socket, 'display_data', {
                                    'data': data_bundle,
                                    'metadata': {},
                                    'transient': {}
                                })
                    elif action == 'restart':
                        await self.main_loop.run_in_executor(None, lambda: self.restart_wolfram_session())
                        if not silent:
                            self.send_response(self.iopub_socket, 'stream', {
                                'name': 'stdout',
                                'text': "Wolfram Language session restarted successfully.\n"
                            })
                    else:
                        if not silent:
                            self.send_response(self.iopub_socket, 'stream', {
                                'name': 'stderr',
                                'text': f"Unknown action: {action}. Supported actions: info, restart\n"
                            })
                elif segment['type'] == 'time':
                    import time
                    seg_count = self.execution_count if wolfram_segment_idx == 0 else 0
                    wolfram_segment_idx += 1
                    
                    py_wall_start = time.perf_counter()
                    
                    func = WLFunction(
                        WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"),
                        segment['content'],
                        seg_count
                    )
                    res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(func))
                    
                    py_wall_end = time.perf_counter()
                    
                    if getattr(self, "_interrupted", False):
                        raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
                        
                    if not isinstance(res, dict):
                        return {
                            'status': 'error',
                            'ename': 'TypeError',
                            'evalue': f'Unexpected return type from evaluator: {type(res)}',
                            'traceback': [str(res)],
                            'execution_count': exec_count
                        }
                        
                    wl_cpu = res.get("WolframCPUTime", 0.0)
                    wl_wall = res.get("WolframWallTime", py_wall_end - py_wall_start)
                    
                    def format_duration(seconds):
                        if seconds < 1e-6:
                            return f"{seconds * 1e9:.2f} ns"
                        elif seconds < 1e-3:
                            return f"{seconds * 1e6:.2f} \u03bcs"
                        elif seconds < 1.0:
                            return f"{seconds * 1e3:.2f} ms"
                        else:
                            return f"{seconds:.2f} s"
                            
                    time_report = (
                        f"CPU times: user {format_duration(wl_cpu)}\n"
                        f"Wall time: {format_duration(wl_wall)}\n"
                    )
                    
                    if not silent:
                        self.send_response(self.iopub_socket, 'stream', {
                            'name': 'stdout',
                            'text': time_report
                        })
                        
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
                            'traceback': list(traceback),
                            'execution_count': exec_count
                        }

                    last_res = res
                    mime_bundles = res.get("mime_bundles", [])
                    exec_count = res.get("execution_count", self.execution_count)
                    
                    if not silent:
                        for bundle in mime_bundles:
                            data = bundle.get("data", {})
                            metadata = bundle.get("metadata", {})
                            
                            if "image/svg+xml" in data:
                                import uuid
                                unique_id = str(uuid.uuid4().hex)[:8]
                                data = dict(data)
                                data["image/svg+xml"] = data["image/svg+xml"].replace("glyph", f"glyph_{unique_id}").replace("clip", f"clip_{unique_id}")
                            
                            if "application/x-wolfram-manipulate" in data:
                                try:
                                    self.create_manipulate_widget(data["application/x-wolfram-manipulate"])
                                except Exception as w_err:
                                    self.log.error(f"Error creating manipulate widget: {w_err}")
                            else:
                                if not execute_result_sent:
                                    self.send_response(self.iopub_socket, 'execute_result', {
                                        'execution_count': exec_count,
                                        'data': data,
                                        'metadata': metadata
                                    })
                                    execute_result_sent = True
                                else:
                                    self.send_response(self.iopub_socket, 'display_data', {
                                        'data': data,
                                        'metadata': metadata,
                                        'transient': {}
                                    })
                elif segment['type'] == 'timeit':
                    import time
                    if segment.get('magic_type') == 'cell':
                        args_str = segment.get('args', '')
                        code_to_time = segment.get('content', '')
                        loops, runs, _ = self._parse_timeit_args(args_str)
                    else:
                        args_and_code = segment.get('args_and_code', '')
                        loops, runs, code_to_time = self._parse_timeit_args(args_and_code)
                        
                    if not code_to_time.strip():
                        if not silent:
                            self.send_response(self.iopub_socket, 'stream', {
                                'name': 'stderr',
                                'text': "Error: No code statement provided to timeit.\n"
                            })
                        continue
                        
                    seg_count = self.execution_count if wolfram_segment_idx == 0 else 0
                    wolfram_segment_idx += 1
                    
                    func = WLFunction(
                        WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"),
                        code_to_time,
                        seg_count
                    )
                    res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(func))
                    
                    if getattr(self, "_interrupted", False):
                        raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
                        
                    if not isinstance(res, dict):
                        return {
                            'status': 'error',
                            'ename': 'TypeError',
                            'evalue': f'Unexpected return type from evaluator: {type(res)}',
                            'traceback': [str(res)],
                            'execution_count': exec_count
                        }
                        
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
                            'traceback': list(traceback),
                            'execution_count': exec_count
                        }
                        
                    calib_time = res.get("WolframWallTime", 0.0)
                    
                    if loops is None:
                        if calib_time < 1e-6:
                            loops = 1000000
                        elif calib_time < 1e-5:
                            loops = 100000
                        elif calib_time < 1e-4:
                            loops = 10000
                        elif calib_time < 1e-3:
                            loops = 1000
                        elif calib_time < 1e-2:
                            loops = 100
                        elif calib_time < 1e-1:
                            loops = 10
                        else:
                            loops = 1
                            
                    code_escaped = code_to_time.replace('\\', '\\\\').replace('"', '\\"')
                    timing_query = f'Block[{{held = ToExpression["{code_escaped}", InputForm, Hold]}}, Quiet[Block[{{$Output = {{}}}}, Timing[AbsoluteTiming[Do[ReleaseHold[held], {{{loops}}}]]]]]]'
                    
                    raw_wall_times = []
                    raw_cpu_times = []
                    
                    for r in range(runs):
                        if getattr(self, "_interrupted", False):
                            raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
                            
                        timing_res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(timing_query))
                        
                        if isinstance(timing_res, (list, tuple)) and len(timing_res) >= 2:
                            cpu_t = timing_res[0]
                            wall_t = timing_res[1][0] if isinstance(timing_res[1], (list, tuple)) else 0.0
                            raw_cpu_times.append(cpu_t)
                            raw_wall_times.append(wall_t)
                        else:
                            raw_cpu_times.append(0.0)
                            raw_wall_times.append(calib_time * loops)
                            
                    wall_times_per_loop = [t / loops for t in raw_wall_times]
                    
                    import math
                    mean = sum(wall_times_per_loop) / len(wall_times_per_loop)
                    variance = sum((x - mean) ** 2 for x in wall_times_per_loop) / len(wall_times_per_loop)
                    stddev = math.sqrt(variance)
                    
                    def format_duration(seconds):
                        if seconds < 1e-9:
                            return f"{seconds * 1e12:.2f} ps"
                        elif seconds < 1e-6:
                            return f"{seconds * 1e9:.2f} ns"
                        elif seconds < 1e-3:
                            return f"{seconds * 1e6:.2f} \u03bcs"
                        elif seconds < 1.0:
                            return f"{seconds * 1e3:.2f} ms"
                        else:
                            return f"{seconds:.2f} s"
                            
                    report = f"{format_duration(mean)} \u00b1 {format_duration(stddev)} per loop (mean \u00b1 stddev of {runs} runs, {loops} loops each)\n"
                    
                    if not silent:
                        self.send_response(self.iopub_socket, 'stream', {
                            'name': 'stdout',
                            'text': report
                        })
                elif segment['type'] == 'wolfram':
                    seg_count = self.execution_count if wolfram_segment_idx == 0 else 0
                    wolfram_segment_idx += 1
                    
                    func = WLFunction(
                        WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"),
                        segment['content'],
                        seg_count
                    )
                    res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(func))

                    if getattr(self, "_interrupted", False):
                        # 交由下方 except 块统一处理（即使没有异常抛出）
                        raise KeyboardInterrupt("Evaluation aborted by user interrupt.")
                    
                    if not isinstance(res, dict):
                        # Fallback in case evaluation returned something unexpected
                        return {
                            'status': 'error',
                            'ename': 'TypeError',
                            'evalue': f'Unexpected return type from evaluator: {type(res)}',
                            'traceback': [str(res)],
                            'execution_count': exec_count
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
                            'traceback': list(traceback),
                            'execution_count': exec_count
                        }

                    last_res = res
                    mime_bundles = res.get("mime_bundles", [])
                    exec_count = res.get("execution_count", self.execution_count)
                    
                    if not silent:
                        for bundle in mime_bundles:
                            data = bundle.get("data", {})
                            metadata = bundle.get("metadata", {})
                            
                            # Prevent SVG ID collisions in browser rendering
                            if "image/svg+xml" in data:
                                import uuid
                                unique_id = str(uuid.uuid4().hex)[:8]
                                data = dict(data)
                                data["image/svg+xml"] = data["image/svg+xml"].replace("glyph", f"glyph_{unique_id}").replace("clip", f"clip_{unique_id}")
                            
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
                            
                            if not execute_result_sent:
                                self.send_response(self.iopub_socket, 'execute_result', {
                                    'execution_count': exec_count,
                                    'data': data,
                                    'metadata': metadata
                                })
                                execute_result_sent = True
                            else:
                                self.send_response(self.iopub_socket, 'display_data', {
                                    'data': data,
                                    'metadata': metadata,
                                    'transient': {}
                                })

            evaluated_user_expr = {}
            if user_expressions and last_res and last_res.get("status") == "ok":
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
        try:
            func = WLFunction(WLSymbol("WolframLanguageForJupyter`getCompletions"), code, cursor_pos)
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
