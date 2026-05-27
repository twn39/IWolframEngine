#!/usr/bin/env wolframscript

(* Load the package files with correct context *)
projectDir = FileNameJoin[{DirectoryName[DirectoryName[$InputFileName]], "WolframLanguageForJupyter", "Resources"}];

(* Mock CopyFile to intercept the dummy connection file in Initialization.wl *)
Unprotect[CopyFile];
CopyFile[src_String, dest_, opts___] /; StringEndsQ[src, "-linkmode"] || !FileExistsQ[src] := (
  Export[dest, Association[
    "key" -> "testkey",
    "transport" -> "tcp",
    "ip" -> "127.0.0.1",
    "hb_port" -> "12345",
    "iopub_port" -> "12346",
    "control_port" -> "12347",
    "stdin_port" -> "12348",
    "shell_port" -> "12349"
  ], "JSON"];
  dest
);
Protect[CopyFile];

(* Mock SocketOpen and LocalSubmit to avoid network binds *)
Needs["ZeroMQLink`"];
Unprotect[ZeroMQLink`SocketOpen];
ZeroMQLink`SocketOpen[___] := "mockSocket";
Protect[ZeroMQLink`SocketOpen];

Unprotect[LocalSubmit];
LocalSubmit[___] := "mockTask";
Protect[LocalSubmit];

(* Load the package files *)
BeginPackage["WolframLanguageForJupyter`"];
Get[FileNameJoin[{Global`projectDir, "Initialization.wl"}]];
Get[FileNameJoin[{Global`projectDir, "CompletionUtilities.wl"}]];
Get[FileNameJoin[{Global`projectDir, "OutputHandlingUtilities.wl"}]];
EndPackage[];

(* Resolve symbols *)
getCompletions = WolframLanguageForJupyter`getCompletions;


testCases = {
  (* 1. Built-in function completion *)
  {"1 + Pl", 4, {"Plot", "Plot3D"}, True},
  
  (* 2. Unicode escape character prefix completion *)
  {"1 + \\[Al", 4, {"\[Alpha]", "\[Aleph]"}, True},

  
  (* 3. Context specific completion *)
  {"Developer`To", 0, {"Developer`ToPackedArray"}, True},
  
  (* 4. No completion case *)
  {"1 + 2", 5, {}, False},

  (* 5. Option name completion *)
  {"Plot[Sin[x], {x, 0, Pi}, PlotSty", 25, {"PlotStyle"}, True}
};

success = True;

Do[
  code = tc[[1]];
  expectedStart = tc[[2]];
  expectedSamples = tc[[3]];
  expectMatch = tc[[4]];
  
  Print["--- Testing Autocomplete: ", InputForm[code], " ---"];
  res = getCompletions[code, StringLength[code]];
  
  If[!AssociationQ[res],
    Print["FAILED! Expected Association, got: ", InputForm[res]];
    success = False;
    Continue[];
  ];
  
  Print["Matches count: ", Length[res["matches"]]];
  Print["Cursor start: ", res["cursor_start"], " (Expected: ", expectedStart, ")"];
  Print["Cursor end: ", res["cursor_end"], " (Expected: ", StringLength[code], ")"];
  
  If[res["cursor_start"] != expectedStart,
    Print["FAILED! Expected cursor_start: ", expectedStart, ", got: ", res["cursor_start"]];
    success = False;
  ];
  
  If[res["cursor_end"] != StringLength[code],
    Print["FAILED! Expected cursor_end: ", StringLength[code], ", got: ", res["cursor_end"]];
    success = False;
  ];
  
  If[expectMatch,
    If[Length[res["matches"]] == 0,
      Print["FAILED! Expected matches but got none."];
      success = False;
    ];
    If[Length[expectedSamples] > 0,
      matchedAll = AllTrue[expectedSamples, MemberQ[res["matches"], #]&];
      Print["Contains expected sample matches? ", matchedAll];
      If[!matchedAll,
        Print["FAILED! Expected samples: ", expectedSamples, ", matches: ", Take[res["matches"], UpTo[5]]];
        success = False;
      ];
    ];
  ,
    If[Length[res["matches"]] > 0,
      Print["FAILED! Expected 0 matches, got: ", res["matches"]];
      success = False;
    ];
  ];
  ,
  {tc, testCases}
];

If[success,
  Print["\nAll autocomplete tests passed successfully!"];
  Exit[0];,
  Print["\nSome autocomplete tests failed."];
  Exit[1];
]
