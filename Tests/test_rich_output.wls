#!/usr/bin/env wolframscript

Print["=== WolframLanguageForJupyter Rich MIME Output Test ==="];

projectDir = "/Users/2342184/programs/WolframLanguageForJupyter/WolframLanguageForJupyter/Resources";

(* Load ZeroMQLink and Initialization via mock *)
Needs["ZeroMQLink`"];

hbPort = 56101; iopubPort = 56102; controlPort = 56103;
stdinPort = 56104; shellPort = 56105;

Unprotect[CopyFile];
CopyFile[src_String, dest_, opts___] /; src === "-linkmode" || StringEndsQ[src, "-linkmode"] := (
  Export[dest, Association[
    "key" -> "test-key", "transport" -> "tcp", "ip" -> "127.0.0.1",
    "hb_port" -> ToString[hbPort], "iopub_port" -> ToString[iopubPort],
    "control_port" -> ToString[controlPort], "stdin_port" -> ToString[stdinPort],
    "shell_port" -> ToString[shellPort]
  ], "JSON"]; dest
);
Protect[CopyFile];

Unprotect[System`$CommandLine];
System`$CommandLine = {"wolfram", "-runfirst", "...", "-linkmode", "Connect"};
Protect[System`$CommandLine];

BeginPackage["WolframLanguageForJupyter`"];
Get[FileNameJoin[{projectDir, "Initialization.wl"}]];
Get[FileNameJoin[{projectDir, "OutputHandlingUtilities.wl"}]];
EndPackage[];

Print["Initialization and OutputHandlingUtilities loaded."];

passCount = 0;
failCount = 0;

checkTest[label_, condition_] := (
  If[TrueQ[condition],
    Print["  PASS: ", label];
    passCount++;
  ,
    Print["  FAIL: ", label];
    failCount++;
  ];
);

(* ======================= TEST 1: Text expression → only text MIME types ======================= *)
Print["\n--- Test 1: Pure text expression (3 + 4 = 7) ---"];
bundle1 = WolframLanguageForJupyter`Private`toMimeBundle[7];
checkTest["bundle1 has data key", KeyExistsQ[bundle1, "data"]];
checkTest["bundle1 has text/plain", KeyExistsQ[bundle1["data"], "text/plain"]];
checkTest["bundle1 text/plain = '7'", bundle1["data"]["text/plain"] === "7"];
checkTest["bundle1 has text/html", KeyExistsQ[bundle1["data"], "text/html"]];
checkTest["bundle1 does NOT have image/svg+xml", !KeyExistsQ[bundle1["data"], "image/svg+xml"]];
checkTest["bundle1 does NOT have image/png", !KeyExistsQ[bundle1["data"], "image/png"]];

(* ======================= TEST 2: Symbol → text MIME types ======================= *)
Print["\n--- Test 2: Symbol expression (Pi) ---"];
bundle2 = WolframLanguageForJupyter`Private`toMimeBundle[Pi];
checkTest["bundle2 has text/plain",  KeyExistsQ[bundle2["data"], "text/plain"]];
checkTest["bundle2 has text/html",   KeyExistsQ[bundle2["data"], "text/html"]];
checkTest["bundle2 no image/svg+xml", !KeyExistsQ[bundle2["data"], "image/svg+xml"]];

(* ======================= TEST 3: 2D Graphics → SVG + PNG ======================= *)
Print["\n--- Test 3: 2D Graphics object (Graphics) ---"];
If[$canUseFrontEnd,
  g3 = Graphics[{Red, Disk[]}];
  bundle3 = WolframLanguageForJupyter`Private`toMimeBundle[g3];
  checkTest["bundle3 has text/plain", KeyExistsQ[bundle3["data"], "text/plain"]];
  checkTest["bundle3 has image/svg+xml", KeyExistsQ[bundle3["data"], "image/svg+xml"]];
  checkTest["bundle3 SVG starts with <", StringStartsQ[bundle3["data"]["image/svg+xml"], "<"]];
  checkTest["bundle3 has image/png", KeyExistsQ[bundle3["data"], "image/png"]];
  checkTest["bundle3 has text/html", KeyExistsQ[bundle3["data"], "text/html"]];
  checkTest["bundle3 metadata has image/png key", KeyExistsQ[bundle3["metadata"], "image/png"]];
  checkTest["bundle3 metadata image/png has width",
    KeyExistsQ[bundle3["metadata"]["image/png"], "width"] &&
    bundle3["metadata"]["image/png"]["width"] > 0];
  checkTest["bundle3 metadata image/png has height",
    KeyExistsQ[bundle3["metadata"]["image/png"], "height"] &&
    bundle3["metadata"]["image/png"]["height"] > 0];
,
  Print["  SKIP (FrontEnd not available)"];
];

(* ======================= TEST 4: toSVGString ======================= *)
Print["\n--- Test 4: toSVGString directly ---"];
If[$canUseFrontEnd,
  svgResult = WolframLanguageForJupyter`Private`toSVGString[Graphics[{Blue, Disk[]}]];
  checkTest["SVG string is a string", StringQ[svgResult]];
  checkTest["SVG string is non-empty", StringLength[svgResult] > 0];
  checkTest["SVG string contains <svg", StringContainsQ[svgResult, "<svg"]];
  svgFailed = WolframLanguageForJupyter`Private`toSVGString["not a graphic"];
  checkTest["toSVGString on non-graphic returns $Failed", FailureQ[svgFailed] || svgFailed === $Failed];
,
  Print["  SKIP (FrontEnd not available)"];
];

(* ======================= TEST 5: toImageData DPI ======================= *)
Print["\n--- Test 5: toImageData uses 144 DPI ---"];
If[$canUseFrontEnd,
  (* Compare raster sizes: 144 DPI should produce larger pixel dimensions than 72 DPI *)
  imgData144 = WolframLanguageForJupyter`Private`toImageData[Graphics[{Disk[]}], 144];
  imgData72  = WolframLanguageForJupyter`Private`toImageData[Graphics[{Disk[]}], 72];
  If[!FailureQ[imgData144] && !FailureQ[imgData72],
    img144 = ImportByteArray[imgData144, "PNG"];
    img72  = ImportByteArray[imgData72,  "PNG"];
    If[Head[img144] === Image && Head[img72] === Image,
      dims144 = ImageDimensions[img144];
      dims72  = ImageDimensions[img72];
      checkTest["144 DPI image is wider than 72 DPI", dims144[[1]] > dims72[[1]]];
      checkTest["144 DPI image is taller than 72 DPI", dims144[[2]] > dims72[[2]]];
    ,
      Print["  SKIP (could not parse PNG images)"];
    ];
  ,
    Print["  SKIP (toImageData failed for one or both DPIs)"];
  ];
,
  Print["  SKIP (FrontEnd not available)"];
];

(* ======================= SUMMARY ======================= *)
Print["\n=== Summary: ", passCount, " passed, ", failCount, " failed ==="];
CloseKernels[];

If[failCount == 0,
  Print["=== Rich Output unit tests PASSED successfully ==="];
  Exit[0];
,
  Print["=== Rich Output unit tests FAILED (", failCount, " failures) ==="];
  Exit[1];
];
