#!/usr/bin/env wolframscript

(* Load the package files with correct context *)
projectDir = FileNameJoin[{DirectoryName[DirectoryName[$InputFileName]], "WolframLanguageForJupyter", "Resources"}];

BeginPackage["WolframLanguageForJupyter`"];
(* Mock values needed by package initialization *)
WolframLanguageForJupyter`Private`keyString = "testkey";
Get[FileNameJoin[{Global`projectDir, "SocketUtilities.wl"}]];
Get[FileNameJoin[{Global`projectDir, "MessagingUtilities.wl"}]];
EndPackage[];

getFrameAssoc = WolframLanguageForJupyter`getFrameAssoc;

(* Test cases *)
testCases = {
  (* Case 1: Simple message *)
  StringToByteArray["uuid-1234<IDS|MSG>sig123{\"msg_id\":\"1\"}{\"parent\":\"none\"}{\"meta\":\"empty\"}{\"code\":\"Print[1]\"}"],
  
  (* Case 2: Nested JSON in content *)
  StringToByteArray["uuid-1234<IDS|MSG>sig123{\"msg_id\":\"1\"}{\"parent\":\"none\"}{\"meta\":\"empty\"}{\"code\":\"Print[{\\\"nested\\\": 1}]\"}"],
  
  (* Case 3: Nested JSON in header *)
  StringToByteArray["uuid-1234<IDS|MSG>sig123{\"msg_id\":\"1\",\"user\":{\"id\":123}}{\"parent\":\"none\"}{\"meta\":\"empty\"}{\"code\":\"Print[1]\"}"],
  
  (* Case 4: Unbalanced brackets in strings *)
  StringToByteArray["uuid-1234<IDS|MSG>sig123{\"msg_id\":\"1\",\"session\":\"abc}def\"}{\"parent\":\"none\"}{\"meta\":\"empty\"}{\"code\":\"Print[1]\"}"],
  
  (* Case 5: Message with trailing data *)
  StringToByteArray["uuid-1234<IDS|MSG>sig123{\"msg_id\":\"1\"}{\"parent\":\"none\"}{\"meta\":\"empty\"}{\"code\":\"Print[1]\"}extrabinarydatahere"]
};

success = True;

Do[
  Print["--- Test Case ", idx, " ---"];
  res = getFrameAssoc[testCases[[idx]]];
  If[!AssociationQ[res],
    Print["FAILED! Expected Association, got: ", InputForm[res]];
    success = False;,
    Print["SUCCESS!"];
    Print["Parsed Keys: ", Keys[res]];
    Print["Ident: ", ByteArrayToString[res["ident"]]];
    Print["Header: ", res["header"]];
    Print["Content: ", res["content"]];
  ],
  {idx, Length[testCases]}
];

If[success,
  Print["\nAll tests passed successfully!"];
  Exit[0];,
  Print["\nSome tests failed."];
  Exit[1];
]
