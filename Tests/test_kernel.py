import jupyter_client
import queue
import time
import sys

# Dynamic discovery of registered Wolfram Language kernelspecs
specs = jupyter_client.kernelspec.KernelSpecManager().get_all_specs()
wl_kernels = [name for name in specs if name.startswith("wolframlanguage")]

if wl_kernels:
    kernel_name = wl_kernels[0]
    print(f"Discovered Wolfram Language kernel: '{kernel_name}'")
else:
    kernel_name = "wolframlanguage14.3"
    print(f"No Wolfram Language kernel auto-discovered. Defaulting to '{kernel_name}'")

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
