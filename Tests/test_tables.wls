#!/usr/bin/env wolframscript

Print["=== WolframLanguageForJupyter Table Beautification Test ==="];

projectDir = "/Users/2342184/programs/WolframLanguageForJupyter/WolframLanguageForJupyter/Resources";
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
Get[FileNameJoin[{Global`projectDir, "Initialization.wl"}]];
Get[FileNameJoin[{Global`projectDir, "OutputHandlingUtilities.wl"}]];
EndPackage[];

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

(* ======================= TEST 1: Dataset (List of Associations) ======================= *)
Print["\n--- Test 1: Dataset List of Associations ---"];
ds1 = Dataset[{<|"a" -> 1, "b" -> x^2|>, <|"a" -> 3, "b" -> 4|>}];
bundle1 = WolframLanguageForJupyter`toMimeBundle[ds1];

checkTest["bundle1 has text/html", KeyExistsQ[bundle1["data"], "text/html"]];
html1 = bundle1["data"]["text/html"];
checkTest["html1 has wolfram-table class", StringContainsQ[html1, "class=\"wolfram-table\""]];
checkTest["html1 has inline MathJax for x^2", StringContainsQ[html1, "$x^2$"]];
checkTest["html1 has row indices", StringContainsQ[html1, ">1</td>"] && StringContainsQ[html1, ">2</td>"]];
checkTest["html1 has headers", StringContainsQ[html1, "<th>a</th>"] && StringContainsQ[html1, "<th>b</th>"]];

(* ======================= TEST 2: Dataset (Single Association) ======================= *)
Print["\n--- Test 2: Dataset Single Association ---"];
ds2 = Dataset[<|"key1" -> "val1", "key2" -> Integrate[y, y]|>];
bundle2 = WolframLanguageForJupyter`toMimeBundle[ds2];

checkTest["bundle2 has text/html", KeyExistsQ[bundle2["data"], "text/html"]];
html2 = bundle2["data"]["text/html"];
checkTest["html2 has Key and Value headers", StringContainsQ[html2, "<th>Key</th>"] && StringContainsQ[html2, "<th>Value</th>"]];
checkTest["html2 has key1 and key2 keys", StringContainsQ[html2, "key1</td>"] && StringContainsQ[html2, "key2</td>"]];
checkTest["html2 has math formatting for integral of y dy", StringContainsQ[html2, "$"] && StringContainsQ[html2, "\\frac"]];

(* ======================= TEST 3: TableForm with Headings ======================= *)
Print["\n--- Test 3: TableForm with custom headings ---"];
tf = TableForm[{{1, 2}, {3, 4}}, TableHeadings -> {{"row1", "row2"}, {"col1", "col2"}}];
bundle3 = WolframLanguageForJupyter`toMimeBundle[tf];

checkTest["bundle3 has text/html", KeyExistsQ[bundle3["data"], "text/html"]];
html3 = bundle3["data"]["text/html"];
checkTest["html3 has row1 row2 headings", StringContainsQ[html3, "row1</td>"] && StringContainsQ[html3, "row2</td>"]];
checkTest["html3 has col1 col2 headings", StringContainsQ[html3, "<th>col1</th>"] && StringContainsQ[html3, "<th>col2</th>"]];

(* ======================= TEST 4: Grid with spans ======================= *)
Print["\n--- Test 4: Grid with SpanFromLeft ---"];
grid = Grid[{{1, SpanFromLeft}, {3, 4}}];
bundle4 = WolframLanguageForJupyter`toMimeBundle[grid];

checkTest["bundle4 has text/html", KeyExistsQ[bundle4["data"], "text/html"]];
html4 = bundle4["data"]["text/html"];
checkTest["html4 has colspan='2'", StringContainsQ[html4, "colspan=\"2\""]];
checkTest["html4 has wolfram-table class", StringContainsQ[html4, "class=\"wolfram-table\""]];

(* ======================= TEST 5: Table Truncation & Footer Summary ======================= *)
Print["\n--- Test 5: Table Truncation & Dimension Summary Footers ---"];

(* Large Dataset *)
dsLarge = Dataset[Table[<|"a" -> i, "b" -> i^2|>, {i, 1, 100}]];
bundle5 = WolframLanguageForJupyter`toMimeBundle[dsLarge];
checkTest["bundle5 has text/html", KeyExistsQ[bundle5["data"], "text/html"]];
html5 = bundle5["data"]["text/html"];
checkTest["html5 contains ellipsis row with colspan", StringContainsQ[html5, "colspan=\"3\""] && StringContainsQ[html5, "...</td>"]];
checkTest["html5 contains dimension summary footer", StringContainsQ[html5, "[100 rows x 2 columns]"]];

(* Large TableForm *)
tfLarge = TableForm[Table[{i, i^2}, {i, 1, 100}]];
bundle6 = WolframLanguageForJupyter`toMimeBundle[tfLarge];
checkTest["bundle6 has text/html", KeyExistsQ[bundle6["data"], "text/html"]];
html6 = bundle6["data"]["text/html"];
checkTest["html6 contains ellipsis row with colspan", StringContainsQ[html6, "colspan=\"2\""] && StringContainsQ[html6, "...</td>"]];
checkTest["html6 contains dimension summary footer", StringContainsQ[html6, "[100 rows x 2 columns]"]];

(* Large Grid *)
gridLarge = Grid[Table[{i, i^2}, {i, 1, 100}]];
bundle7 = WolframLanguageForJupyter`toMimeBundle[gridLarge];
checkTest["bundle7 has text/html", KeyExistsQ[bundle7["data"], "text/html"]];
html7 = bundle7["data"]["text/html"];
checkTest["html7 contains ellipsis row with colspan", StringContainsQ[html7, "colspan=\"2\""] && StringContainsQ[html7, "..."]];
checkTest["html7 contains dimension summary footer", StringContainsQ[html7, "[100 rows x 2 columns]"]];

(* ======================= Summary ======================= *)
Print["\n=== Summary: ", passCount, " passed, ", failCount, " failed ==="];
If[failCount > 0, Exit[1], Exit[0]];
