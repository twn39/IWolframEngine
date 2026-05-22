import os
import re
import sys
import json
from ipykernel.kernelbase import Kernel
from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language.expression import WLFunction, WLSymbol

def clean_wolfram_boxes(text):
    text = re.sub(r'[\uf7c0-\uf7c9]', '', text)
    text = re.sub(r'[\uf3c0-\uf3c9]', '', text)
    
    token_pattern = re.compile(r'\"(?:[^\"\\]|\\.)*\"|[a-zA-Z]+Box|[\[\]\{\}\,]|[^\"a-zA-Z\[\]\{\}\,]+')
    tokens = token_pattern.findall(text)
    
    def parse_expr(tokens, idx):
        if idx >= len(tokens):
            return "", idx
        token = tokens[idx]
        if token.startswith('"'):
            val = token[1:-1].replace('\\"', '"')
            return val, idx + 1
        elif token in ('RowBox', 'StyleBox', 'SubscriptBox', 'SuperscriptBox', 'FractionBox', 'OverscriptBox', 'UnderscriptBox'):
            if idx + 1 < len(tokens) and tokens[idx + 1] == '[':
                args = []
                curr = idx + 2
                while curr < len(tokens) and tokens[curr] != ']':
                    if tokens[curr] == '{':
                        list_items = []
                        curr += 1
                        while curr < len(tokens) and tokens[curr] != '}':
                            if tokens[curr] == ',':
                                curr += 1
                                continue
                            if tokens[curr].isspace():
                                curr += 1
                                continue
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
                else:
                    return "".join(args), curr
            return token, idx + 1
        elif token in ('[', ']', '{', '}', ','):
            return "", idx + 1
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
        self.wl_session = None
        self.start_wolfram_session()

    def start_wolfram_session(self):
        kernel_path = find_wolfram_kernel()
        if not kernel_path:
            self.log.error("Could not find a valid Wolfram Kernel path. Please set WOLFRAM_KERNEL_PATH.")
            raise RuntimeError("Wolfram Kernel not found.")
        
        self.log.info(f"Starting Wolfram Language session with kernel: {kernel_path}")
        self.wl_session = WolframLanguageSession(kernel_path)
        self.wl_session.start()
        
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

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {
                'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
            }
            
        try:
            func = WLFunction(WLSymbol("WolframLanguageForJupyter`evaluateAndFormat"), code)
            res = self.wl_session.evaluate(func)
            
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

        except Exception as e:
            self.log.error(f"Execution error: {e}")
            return {
                'status': 'error',
                'ename': type(e).__name__,
                'evalue': str(e),
                'traceback': []
            }

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

    def do_inspect(self, code, cursor_pos, detail_level=0):
        pattern = re.compile(r'[a-zA-Z\$`][a-zA-Z0-9\$`]*')
        symbol = None
        for match in pattern.finditer(code):
            if match.start() <= cursor_pos <= match.end():
                symbol = match.group(0)
                break
                
        if not symbol:
            return {'status': 'ok', 'found': False, 'data': {}, 'metadata': {}}
            
        try:
            msg_expr = WLFunction(WLSymbol("MessageName"), WLFunction(WLSymbol("Symbol"), symbol), "usage")
            usage = self.wl_session.evaluate(msg_expr)
            
            if usage and isinstance(usage, str):
                if usage.endswith("::usage") or usage == "$Failed":
                    return {'status': 'ok', 'found': False, 'data': {}, 'metadata': {}}
                
                cleaned_usage = clean_wolfram_boxes(usage)
                return {
                    'status': 'ok',
                    'found': True,
                    'data': {
                        'text/plain': cleaned_usage
                    },
                    'metadata': {}
                }
        except Exception as e:
            self.log.error(f"Error in do_inspect: {e}")
            
        return {'status': 'ok', 'found': False, 'data': {}, 'metadata': {}}

    def do_shutdown(self, restart):
        if self.wl_session:
            try:
                self.wl_session.terminate()
            except Exception as e:
                self.log.warning(f"Error terminating Wolfram session: {e}")
        return super().do_shutdown(restart)

if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=WolframLanguageKernel)
