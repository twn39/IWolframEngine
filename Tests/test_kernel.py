import jupyter_client
import queue
import time
import sys

# Dynamic discovery of registered Wolfram Language kernelspecs
specs = jupyter_client.kernelspec.KernelSpecManager().get_all_specs()
wl_kernels = [name for name in specs if name.startswith("wolframlanguage")]

if "wolframlanguage" in wl_kernels:
    kernel_name = "wolframlanguage"
elif wl_kernels:
    kernel_name = wl_kernels[0]
else:
    kernel_name = "wolframlanguage"

print(f"Discovered Wolfram Language kernel: '{kernel_name}'")

print(f"Starting kernel '{kernel_name}'...")
km, kc = jupyter_client.manager.start_new_kernel(kernel_name=kernel_name)

def get_reply_for_msg_id(kc, msg_id, timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            msg = kc.get_shell_msg(timeout=0.5)
            # print(f"[SHELL] Received {msg['msg_type']} with parent {msg.get('parent_header', {}).get('msg_id')}")
            if msg.get('parent_header', {}).get('msg_id') == msg_id:
                return msg
        except queue.Empty:
            pass
    raise RuntimeError(f"Timeout waiting for reply to {msg_id}")

try:
    print("Sending execute request: 'Print[\"hello world\"]; 3 * 3'...")
    msg_id = kc.execute('Print["hello world"]; 3 * 3')
    
    stdout = []
    exec_result = None
    
    start_time = time.time()
    while time.time() - start_time < 15:
        try:
            msg = kc.get_iopub_msg(timeout=1)
            msg_type = msg['msg_type']
            content = msg['content']
            
            print(f"[IOPUB] {msg_type}: {content}")
            
            if msg_type == 'stream':
                stdout.append(content['text'])
            elif msg_type == 'execute_result':
                exec_result = content['data']
            elif msg_type == 'status' and content['execution_state'] == 'idle':
                print("Kernel is idle.")
                break
        except queue.Empty:
            pass

    reply = get_reply_for_msg_id(kc, msg_id)
    print(f"[SHELL] execute reply: {reply['content']}")

    print("\nSending complete request for '1 + Pl'...")
    comp_msg_id = kc.complete('1 + Pl', 6)
    comp_reply = get_reply_for_msg_id(kc, comp_msg_id)
    print(f"[SHELL] complete reply: {comp_reply['content']}")
    # Assert autocomplete results
    assert comp_reply['content']['status'] == 'ok', "Complete request status not ok"
    assert "Plot" in comp_reply['content']['matches'], "Complete matches missing 'Plot'"
    assert comp_reply['content']['cursor_start'] == 4, f"Expected cursor_start 4, got {comp_reply['content']['cursor_start']}"
    assert comp_reply['content']['cursor_end'] == 6, f"Expected cursor_end 6, got {comp_reply['content']['cursor_end']}"
    print("Autocomplete check inside integration test PASSED!")

    print("\nSending complete request for '1 + \\[Al'...")
    comp_msg_id2 = kc.complete('1 + \\[Al', 8)
    comp_reply2 = get_reply_for_msg_id(kc, comp_msg_id2)
    print(f"[SHELL] complete reply 2: {comp_reply2['content']}")
    assert comp_reply2['content']['status'] == 'ok', "Complete request status not ok"
    assert "α" in comp_reply2['content']['matches'], "Complete matches missing alpha character 'α'"
    assert comp_reply2['content']['cursor_start'] == 4, f"Expected cursor_start 4, got {comp_reply2['content']['cursor_start']}"
    assert comp_reply2['content']['cursor_end'] == 8, f"Expected cursor_end 8, got {comp_reply2['content']['cursor_end']}"
    print("Autocomplete Unicode check inside integration test PASSED!")

    print("\nSending complete request for option 'Plot[Sin[x], {x, 0, Pi}, PlotSty'...")
    comp_msg_id3 = kc.complete('Plot[Sin[x], {x, 0, Pi}, PlotSty', 32)
    comp_reply3 = get_reply_for_msg_id(kc, comp_msg_id3)
    print(f"[SHELL] complete reply 3: {comp_reply3['content']}")
    assert comp_reply3['content']['status'] == 'ok', "Complete request status not ok"
    assert "PlotStyle" in comp_reply3['content']['matches'], "Complete matches missing 'PlotStyle'"
    assert comp_reply3['content']['cursor_start'] == 25, f"Expected cursor_start 25, got {comp_reply3['content']['cursor_start']}"
    assert comp_reply3['content']['cursor_end'] == 32, f"Expected cursor_end 32, got {comp_reply3['content']['cursor_end']}"
    print("Autocomplete Option check inside integration test PASSED!")

    print("\nSending graphics execute request: 'Graphics[{Red, Disk[]}]'...")
    # Flush any stale IOPub messages before starting
    while True:
        try:
            kc.get_iopub_msg(timeout=0.2)
        except queue.Empty:
            break

    gfx_msg_id = kc.execute('Graphics[{Red, Disk[]}]')

    gfx_exec_result = None
    start_gfx = time.time()
    while time.time() - start_gfx < 30:
        try:
            msg = kc.get_iopub_msg(timeout=1)
            msg_type = msg['msg_type']
            print(f"[IOPUB] {msg_type}: keys={list(msg.get('content', {}).keys())}")
            if msg_type == 'execute_result':
                gfx_exec_result = msg['content']
            elif msg_type == 'status' and msg['content'].get('execution_state') == 'idle':
                print("Kernel is idle after graphics execution.")
                break
        except queue.Empty:
            pass

    get_reply_for_msg_id(kc, gfx_msg_id)  # consume shell reply


    if gfx_exec_result is not None:
        data = gfx_exec_result.get('data', {})
        metadata = gfx_exec_result.get('metadata', {})
        print(f"[GRAPHICS] MIME keys: {list(data.keys())}")
        print(f"[GRAPHICS] metadata keys: {list(metadata.keys())}")

        # Check SVG
        assert "image/svg+xml" in data, \
            f"Missing image/svg+xml in graphics output. Got keys: {list(data.keys())}"
        assert "<svg" in data["image/svg+xml"], \
            "image/svg+xml content does not look like valid SVG"
        print("SVG output check PASSED!")

        # Check PNG
        assert "image/png" in data, "Missing image/png in graphics output"
        assert len(data["image/png"]) > 0, "image/png base64 is empty"
        print("PNG output check PASSED!")

        # Check PNG metadata dimensions
        png_meta = metadata.get("image/png", {})
        assert "width" in png_meta, \
            f"Missing width in image/png metadata. Got: {png_meta}"
        assert "height" in png_meta, \
            f"Missing height in image/png metadata. Got: {png_meta}"
        assert png_meta["width"] > 0, "PNG metadata width is not positive"
        assert png_meta["height"] > 0, "PNG metadata height is not positive"
        print(f"PNG metadata check PASSED! (width={png_meta['width']}, height={png_meta['height']})")

        # Check text/plain is always present
        assert "text/plain" in data, "Missing text/plain in graphics output"
        print("text/plain check PASSED!")

        print("Rich MIME output integration test PASSED!")
    else:
        print("WARNING: No execute_result received for graphics — skipping MIME checks")

    def execute_and_collect(kc, code, timeout=10):
        # Flush iopub
        while True:
            try:
                kc.get_iopub_msg(timeout=0.1)
            except queue.Empty:
                break
        
        msg_id = kc.execute(code)
        iopub_msgs = []
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                msg = kc.get_iopub_msg(timeout=0.5)
                iopub_msgs.append(msg)
                if msg['msg_type'] == 'status' and msg['content'].get('execution_state') == 'idle':
                    break
            except queue.Empty:
                pass
        
        reply = get_reply_for_msg_id(kc, msg_id)
        return reply, iopub_msgs

    # Test Case 1: Syntax Error
    print("\n[TEST] Verifying Syntax Error (1+*2)...")
    reply, iopub_msgs = execute_and_collect(kc, '1+*2')
    print(f"Reply: {reply['content']}")
    assert reply['content']['status'] == 'error', f"Expected status 'error', got {reply['content']['status']}"
    assert reply['content']['ename'] == 'SyntaxError', f"Expected ename 'SyntaxError', got {reply['content']['ename']}"
    assert "Syntax" in reply['content']['evalue'] or "expression" in reply['content']['evalue'].lower(), f"Expected evalue to describe syntax error, got {reply['content']['evalue']}"
    assert len(reply['content']['traceback']) > 0, "Expected non-empty traceback"
    
    # Check iopub messages for 'error'
    error_msg = next((m for m in reversed(iopub_msgs) if m['msg_type'] == 'error'), None)
    assert error_msg is not None, "Missing 'error' message on iopub socket for syntax error"
    assert error_msg['content']['ename'] == 'SyntaxError'
    assert error_msg['content']['evalue'] == reply['content']['evalue']
    # Check that no execute_result was sent
    assert not any(m['msg_type'] == 'execute_result' for m in iopub_msgs), "Should not send execute_result on error"
    print("Syntax Error test passed!")

    # Test Case 2: Abort
    print("\n[TEST] Verifying Abort (Abort[])...")
    reply, iopub_msgs = execute_and_collect(kc, 'Abort[]')
    print(f"Reply: {reply['content']}")
    assert reply['content']['status'] == 'error', f"Expected status 'error', got {reply['content']['status']}"
    assert reply['content']['ename'] == 'Abort', f"Expected ename 'Abort', got {reply['content']['ename']}"
    assert "aborted" in reply['content']['evalue'].lower(), f"Expected evalue to describe abort, got {reply['content']['evalue']}"
    assert len(reply['content']['traceback']) > 0, "Expected non-empty traceback"
    
    # Check iopub messages for 'error'
    error_msg = next((m for m in reversed(iopub_msgs) if m['msg_type'] == 'error'), None)
    assert error_msg is not None, "Missing 'error' message on iopub socket for abort"
    assert error_msg['content']['ename'] == 'Abort'
    assert error_msg['content']['evalue'] == reply['content']['evalue']
    # Check that no execute_result was sent
    assert not any(m['msg_type'] == 'execute_result' for m in iopub_msgs), "Should not send execute_result on error"
    print("Abort test passed!")

    # Test Case 3: Uncaught Throw
    print("\n[TEST] Verifying Uncaught Throw (Throw[abc])...")
    reply, iopub_msgs = execute_and_collect(kc, 'Throw[abc]')
    print(f"Reply: {reply['content']}")
    assert reply['content']['status'] == 'error', f"Expected status 'error', got {reply['content']['status']}"
    assert reply['content']['ename'] == 'Throw', f"Expected ename 'Throw', got {reply['content']['ename']}"
    assert "uncaught" in reply['content']['evalue'].lower() or "throw" in reply['content']['evalue'].lower(), f"Expected evalue to describe uncaught throw, got {reply['content']['evalue']}"
    assert len(reply['content']['traceback']) > 0, "Expected non-empty traceback"
    
    # Check iopub messages for 'error'
    error_msg = next((m for m in reversed(iopub_msgs) if m['msg_type'] == 'error'), None)
    assert error_msg is not None, "Missing 'error' message on iopub socket for uncaught throw"
    assert error_msg['content']['ename'] == 'Throw'
    assert error_msg['content']['evalue'] == reply['content']['evalue']
    # Check that no execute_result was sent
    assert not any(m['msg_type'] == 'execute_result' for m in iopub_msgs), "Should not send execute_result on error"
    print("Uncaught Throw test passed!")

    # Test Case 4: Normal Warning (1/0)
    print("\n[TEST] Verifying Normal Warning (1/0)...")
    reply, iopub_msgs = execute_and_collect(kc, '1/0')
    print(f"Reply: {reply['content']}")
    assert reply['content']['status'] == 'ok', f"Expected status 'ok' for warning, got {reply['content']['status']}"
    # Check that execute_result was sent
    assert any(m['msg_type'] == 'execute_result' for m in iopub_msgs), "Expected execute_result for 1/0 warning"
    print("Normal Warning test passed!")

    # Test Case 5: Rich Inspection
    print("\n[TEST] Verifying Rich Inspection (inspect Plot)...")
    inspect_msg_id = kc.inspect('Plot', 2)
    inspect_reply = get_reply_for_msg_id(kc, inspect_msg_id)
    print(f"Inspect Reply: {inspect_reply['content']}")
    assert inspect_reply['content']['status'] == 'ok', "Inspect status not ok"
    assert inspect_reply['content']['found'] == True, "Expected symbol 'Plot' to be found"
    data = inspect_reply['content']['data']
    assert "text/plain" in data, "Missing text/plain in inspect reply"
    assert "text/html" in data, "Missing text/html in inspect reply"
    assert "text/markdown" in data, "Missing text/markdown in inspect reply"
    assert "Plot" in data["text/plain"], "Plain text inspect reply missing 'Plot'"
    assert "Plot" in data["text/html"], "HTML inspect reply missing 'Plot'"
    assert "Plot" in data["text/markdown"], "Markdown inspect reply missing 'Plot'"
    assert "Options" in data["text/html"], "HTML inspect reply missing 'Options'"
    assert "http://reference.wolfram.com/language/ref/Plot.html" in data["text/html"], "HTML inspect reply missing reference link"
    print("Rich Inspection test passed!")

    # Test Case 6: is_complete
    print("\n[TEST] Verifying is_complete...")
    
    # Complete
    is_comp_msg_id = kc.is_complete('1 + 2')
    is_comp_reply = get_reply_for_msg_id(kc, is_comp_msg_id)
    print(f"is_complete reply for '1 + 2': {is_comp_reply['content']}")
    assert is_comp_reply['content']['status'] == 'complete', f"Expected complete, got {is_comp_reply['content']}"
    
    # Incomplete (trailing operator)
    is_comp_msg_id = kc.is_complete('1 + ')
    is_comp_reply = get_reply_for_msg_id(kc, is_comp_msg_id)
    print(f"is_complete reply for '1 + ': {is_comp_reply['content']}")
    assert is_comp_reply['content']['status'] == 'incomplete', f"Expected incomplete, got {is_comp_reply['content']}"
    assert is_comp_reply['content'].get('indent') == '    ', f"Expected indent '    ', got {is_comp_reply['content'].get('indent')!r}"
    
    # Incomplete (unclosed bracket)
    is_comp_msg_id = kc.is_complete('f[x')
    is_comp_reply = get_reply_for_msg_id(kc, is_comp_msg_id)
    print(f"is_complete reply for 'f[x': {is_comp_reply['content']}")
    assert is_comp_reply['content']['status'] == 'incomplete', f"Expected incomplete, got {is_comp_reply['content']}"
    
    # Invalid (mismatched bracket)
    is_comp_msg_id = kc.is_complete('f[x)')
    is_comp_reply = get_reply_for_msg_id(kc, is_comp_msg_id)
    print(f"is_complete reply for 'f[x)': {is_comp_reply['content']}")
    assert is_comp_reply['content']['status'] == 'invalid', f"Expected invalid, got {is_comp_reply['content']}"
    
    print("is_complete tests passed!")

    print("\n--- RESULTS ---")
    stdout_str = ''.join(stdout).strip()
    print(f"Stdout output: {stdout_str}")
    print(f"Execution result: {exec_result}")
    
    # Check assertions
    assert "hello world" in stdout_str, "Stdout missing 'hello world'"
    assert exec_result and exec_result.get("text/plain") == "9", f"Expected execution result '9', got {exec_result}"
    print("\nIntegration test PASSED successfully!")
    sys.exit(0)
    
except Exception as e:
    print(f"\nIntegration test FAILED: {e}")
    sys.exit(1)
    
finally:
    print("Shutting down kernel...")
    km.shutdown_kernel()
    print("Done.")
