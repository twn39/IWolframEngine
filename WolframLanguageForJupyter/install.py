import json
import os
import sys
import argparse
from jupyter_client.kernelspec import KernelSpecManager
from tempfile import TemporaryDirectory

def install_my_kernel(user=True, prefix=None):
    kernel_name = "wolframlanguage"
    display_name = "Wolfram Language (Python)"
    
    kernel_json = {
        "argv": [
            sys.executable,
            "-m",
            "WolframLanguageForJupyter.kernel",
            "-f",
            "{connection_file}"
        ],
        "display_name": display_name,
        "language": "wolfram"
    }
    
    with TemporaryDirectory() as temp_dir:
        kernel_json_path = os.path.join(temp_dir, "kernel.json")
        with open(kernel_json_path, "w") as f:
            json.dump(kernel_json, f, indent=2)
            
        manager = KernelSpecManager()
        installed_path = manager.install_kernel_spec(
            temp_dir,
            kernel_name=kernel_name,
            user=user,
            prefix=prefix
        )
        print(f"Successfully installed kernel spec for {kernel_name} at {installed_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install Wolfram Language Jupyter Kernel")
    parser.add_argument("--user", action="store_true", default=True, help="Install for the current user (default)")
    parser.add_argument("--sys-prefix", action="store_true", help="Install into sys.prefix")
    parser.add_argument("--prefix", help="Install into the given prefix")
    args = parser.parse_args()
    
    prefix = None
    if args.sys_prefix:
        prefix = sys.prefix
    elif args.prefix:
        prefix = args.prefix
        
    install_my_kernel(user=args.user and not (args.sys_prefix or args.prefix), prefix=prefix)
