#!/usr/bin/env wolframscript

Print["=== WolframLanguageForJupyter Heartbeat Test ==="];

projectDir = "/Users/2342184/programs/WolframLanguageForJupyter/WolframLanguageForJupyter/Resources";

(* Define ports *)
hbPort = 55685;
iopubPort = 55686;
controlPort = 55687;
stdinPort = 55688;
shellPort = 55689;

(* Mock CopyFile to intercept the dummy connection file in Initialization.wl *)
Unprotect[CopyFile];
CopyFile[src_String, dest_, opts___] /; src === "-linkmode" || StringEndsQ[src, "-linkmode"] := (
  Print["[MOCK] CopyFile called for: ", src];
  Export[dest, Association[
    "key" -> "test-key",
    "transport" -> "tcp",
    "ip" -> "127.0.0.1",
    "hb_port" -> ToString[hbPort],
    "iopub_port" -> ToString[iopubPort],
    "control_port" -> ToString[controlPort],
    "stdin_port" -> ToString[stdinPort],
    "shell_port" -> ToString[shellPort]
  ], "JSON"];
  dest
);
Protect[CopyFile];

(* Set command line arguments to trigger CopyFile mock *)
Unprotect[System`$CommandLine];
System`$CommandLine = {"wolfram", "-runfirst", "...", "-linkmode", "Connect"};
Protect[System`$CommandLine];

(* Load ZeroMQLink *)
Needs["ZeroMQLink`"];

Print["Loading Initialization.wl..."];
BeginPackage["WolframLanguageForJupyter`"];
Get[FileNameJoin[{Global`projectDir, "Initialization.wl"}]];
EndPackage[];
Print["Initialization.wl loaded successfully."];

success = False;
If[Head[WolframLanguageForJupyter`Private`hbProcess] === ProcessObject || Head[WolframLanguageForJupyter`Private`hbKernel] === KernelObject,
  Print["Heartbeat forwarder object found and running in the background."];
  Print["Connecting client socket to heartbeat port ", hbPort, "..."];
  client = SocketConnect["tcp://127.0.0.1:" <> ToString[hbPort], "ZMQ_REQ"];
  If[FailureQ[client],
    Print["FAILED to connect to heartbeat socket! Error: ", InputForm[client]];
  ,
    Print["Sending ping 'test-ping-data'..."];
    ZeroMQLink`ZMQSocketWriteMessage[client, StringToByteArray["test-ping-data"], "Multipart" -> False];
    Print["Waiting for heartbeat response..."];
    ready = SocketWaitNext[{client}, 3];
    Print["Ready sockets: ", InputForm[ready]];
    If[Length[ready] > 0,
      reply = SocketReadMessage[client];
      If[Not[FailureQ[reply]],
        Print["SUCCESS! Received heartbeat response: ", ByteArrayToString[reply]];
        If[ByteArrayToString[reply] === "test-ping-data",
          success = True;
        ];
      ];
    ,
      Print["FAILED! Heartbeat did not respond within 3 seconds."];
    ];
    Close[client];
  ];
,
  Print["No heartbeat forwarder object found!"];
];

(* Clean up sockets opened by Initialization.wl *)
Print["Cleaning up sockets and subkernels..."];
Quiet[Close[WolframLanguageForJupyter`Private`ioPubSocket]];
Quiet[Close[WolframLanguageForJupyter`Private`controlSocket]];
Quiet[Close[WolframLanguageForJupyter`Private`inputSocket]];
Quiet[Close[WolframLanguageForJupyter`Private`shellSocket]];

(* Close all subkernels to free up resources *)
CloseKernels[];

If[success,
  Print["=== Heartbeat unit test PASSED successfully ==="];
  Exit[0];
,
  Print["=== Heartbeat unit test FAILED ==="];
  Exit[1];
];
