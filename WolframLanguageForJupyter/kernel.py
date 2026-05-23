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
        self.wl_session = None
        self.main_loop = asyncio.get_event_loop()
        self.stdin_server = StdinServer(self)
        self.stdin_server.start()
        
        self._executing = False
        self._interrupted = False
        
        self.old_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.handle_sigint)
        
        self.start_wolfram_session()

    def handle_sigint(self, signum, frame):
        self.log.info("SIGINT received in Python kernel.")
        if getattr(self, "_executing", False):
            self._interrupted = True
            if self.wl_session:
                try:
                    self.log.info("Terminating running Wolfram session due to interrupt...")
                    self.wl_session.terminate()
                except Exception as e:
                    self.log.warning(f"Failed to terminate session in SIGINT handler: {e}")
        if callable(self.old_sigint_handler):
            try:
                self.old_sigint_handler(signum, frame)
            except KeyboardInterrupt:
                raise

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

    def create_manipulate_widget(self, data):
        import ipywidgets as widgets
        import sys
        from IPython.display import publish_display_data
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
                control = widgets.Dropdown(
                    options=var["choices"],
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
                
                output.clear_output(wait=True)
                with output:
                    if isinstance(eval_res, dict) and eval_res.get("status") == "ok":
                        stdout = eval_res.get("captured_stdout", "")
                        if stdout:
                            sys.stdout.write(stdout)
                            sys.stdout.flush()
                        
                        stderr = eval_res.get("captured_stderr", [])
                        if stderr:
                            sys.stderr.write("\n".join(stderr) + "\n")
                            sys.stderr.flush()
                            
                        mime = eval_res.get("mime_bundle", {})
                        if mime:
                            data_dict = mime.get("data", {})
                            metadata_dict = mime.get("metadata", {})
                            publish_display_data(data=data_dict, metadata=metadata_dict)
                    else:
                        sys.stderr.write(f"Error evaluating Manipulate: {eval_res}\n")
                        sys.stderr.flush()
            except Exception as e:
                output.clear_output(wait=True)
                with output:
                    sys.stderr.write(f"Error in update_output: {e}\n")
                    sys.stderr.flush()
                    
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
            func = WLFunction(WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"), code)
            res = await self.main_loop.run_in_executor(None, lambda: self.wl_session.evaluate(func))
            
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

            # If success, publish execute_result if not silent
            mime_bundle = res.get("mime_bundle")
            exec_count = res.get("execution_count", self.execution_count)
            
            if mime_bundle and "application/x-wolfram-manipulate" in mime_bundle.get("data", {}):
                manipulate_data = mime_bundle["data"]["application/x-wolfram-manipulate"]
                try:
                    widget_box = self.create_manipulate_widget(manipulate_data)
                    mime_bundle = {
                        "data": {
                            "application/vnd.jupyter.widget-view+json": {
                                "version_major": 2,
                                "version_minor": 0,
                                "model_id": widget_box.model_id
                            },
                            "text/plain": repr(widget_box)
                        },
                        "metadata": {}
                    }
                except Exception as w_err:
                    self.log.error(f"Error creating manipulate widget: {w_err}")
            
            if not silent and mime_bundle:
                data = mime_bundle.get("data", {})
                metadata = mime_bundle.get("metadata", {})
                self.send_response(self.iopub_socket, 'execute_result', {
                    'execution_count': exec_count,
                    'data': data,
                    'metadata': metadata
                })

            return {
                'status': 'ok',
                'execution_count': exec_count,
                'payload': [],
                'user_expressions': {},
            }

        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as e:
            if getattr(self, "_interrupted", False):
                self._interrupted = False
                self.restart_wolfram_session()
                self.send_response(self.iopub_socket, 'error', {
                    'ename': 'KeyboardInterrupt',
                    'evalue': 'Execution interrupted by user. The Wolfram Kernel process has been restarted.',
                    'traceback': ['KeyboardInterrupt: Execution interrupted by user. All variables and definitions have been reset.']
                })
                return {
                    'status': 'error',
                    'ename': 'KeyboardInterrupt',
                    'evalue': 'Execution interrupted by user. The Wolfram Kernel process has been restarted.',
                    'traceback': ['KeyboardInterrupt: Execution interrupted by user. All variables and definitions have been reset.']
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
