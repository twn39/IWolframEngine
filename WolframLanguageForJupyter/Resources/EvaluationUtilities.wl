(************************************************
				EvaluationUtilities.wl
*************************************************
Description:
	Utilities for evaluating input arriving
		from Jupyter, and for simulating
		the Mathematica REPL
Symbols defined:
	Print,
	redirectPrint,
	redirectMessages,
	simulatedEvaluate
*************************************************)

(************************************
	Get[] guard
*************************************)

If[
	!TrueQ[WolframLanguageForJupyter`Private`$GotEvaluationUtilities],
	
	WolframLanguageForJupyter`Private`$GotEvaluationUtilities = True;

(************************************
	load required
		WolframLanguageForJupyter
		files
*************************************)

	Get[FileNameJoin[{DirectoryName[$InputFileName], "Initialization.wl"}]]; (* loopState, applyHook, $canUseFrontEnd *)

(************************************
	wrapper for interacting
		with the cloud
*************************************)

	(* Interact is a wrapper, open to the user, for asking that the result of the evaluation
		be displayed as an embedded cloud object  that can be interacted with *)
	(* set Interact to not evaluate its arguments *)
	SetAttributes[Interact, HoldAll];

(************************************
	private symbols
*************************************)

	(* begin the private context for WolframLanguageForJupyter *)
	Begin["`Private`"];

(************************************
	helper utilities for
		diagnosing and removing
		command wrappers
		(e.g., Interact[])
*************************************)

	(* check if expr is wrapped with Interact *)
	interactQ[expr___] := MatchQ[expr, Hold[Interact[___]]];
	SetAttributes[interactQ, HoldAll];

	(* remove any Interact wrappers,
		apply $Pre,
		and bring in the Front End for the evaluation of expr *)
	uninteract[Interact[expr_]] := UsingFrontEnd[applyHook[$Pre, expr]];
	uninteract[expr_] := UsingFrontEnd[applyHook[$Pre, expr]];
	SetAttributes[uninteract, HoldAll];

(************************************
	version of Print that
		sends output to Jupyter
*************************************)

	(* redirect Print calls into a message to Jupyter, in order to print in Jupyter *)
	(* TODO: review other methods: through EvaluationData or WSTP so we don't redefine Print *)
	(* TODO: remove this and just permanently set $Output to {..., loopState["WolframLanguageForJupyter-stdout"], ...} *)
	Unprotect[Print];
	Print[ourArgs___, opts:OptionsPattern[]] :=
		Block[
			{
				$inPrint = True,
				$Output
			},
			If[
				loopState["printFunction"] =!= False,
				$Output = {OpenWrite[FormatType -> OutputForm]};
				If[
					!FailureQ[First[$Output]],
					Print[ourArgs, opts];
					loopState["printFunction"][
						Import[$Output[[1,1]], "String"]
					];
					Close[First[$Output]];
				];
			];
		] /; !TrueQ[$inPrint];
	Protect[Print];

(************************************
	version of Echo that
		sends output to Jupyter
*************************************)

	(* redirect Echo calls into a message to Jupyter, in order to print/echo in Jupyter *)
	Echo[""];
	Unprotect[Echo];
	DownValues[Echo] =
		Prepend[
			DownValues[Echo],
			HoldPattern[Echo[ourArgs___, opts:OptionsPattern[]]] :> Block[{$inEcho = True, $Notebooks = False}, Echo[ourArgs, opts]] /; !TrueQ[$inEcho]
		];
	Protect[Echo];

(************************************
	version of Write that
		sends output to Jupyter
*************************************)

	(* redirect Write["stdout", ourArgs___] calls to Write[loopState["WolframLanguageForJupyter-stdout"], ourArgs___],
		in order to print in Jupyter *)
	Unprotect[Write];
	Write["stdout", ourArgs___, opts:OptionsPattern[]] :=
		Block[
			{
				$inWrite = True
			},
			If[
				loopState["WolframLanguageForJupyter-stdout"] =!= False,
				Write[loopState["WolframLanguageForJupyter-stdout"], ourArgs]
			];
		] /; !TrueQ[$inWrite];
	Protect[Write];
	(* redirect Write[{before___, "stdout", after___}, ourArgs___] calls to
		Write[{before___, "WolframLanguageForJupyter-stdout", after___}, ourArgs___],
		in order to print in Jupyter *)
	Unprotect[Write];
	Write[{before___, "stdout", after___}, ourArgs___, opts:OptionsPattern[]] :=
		Block[
			{
				$inWrite = True
			},
			If[
				loopState["WolframLanguageForJupyter-stdout"] =!= False,
				Write[{before, loopState["WolframLanguageForJupyter-stdout"], after}, ourArgs]
			];
		] /; !TrueQ[$inWrite];
	Protect[Write];

(************************************
	version of WriteString that
		sends output to Jupyter
*************************************)

	(* redirect WriteString["stdout", ourArgs___] calls to WriteString[loopState["WolframLanguageForJupyter-stdout"], ourArgs___],
		in order to print in Jupyter *)
	Unprotect[WriteString];
	WriteString["stdout", ourArgs___, opts:OptionsPattern[]] :=
		Block[
			{
				$inWriteString = True
			},
			If[
				loopState["WolframLanguageForJupyter-stdout"] =!= False,
				WriteString[loopState["WolframLanguageForJupyter-stdout"], ourArgs]
			];
		] /; !TrueQ[$inWriteString];
	Protect[WriteString];
	(* redirect WriteString[{before___, "stdout", after___}, ourArgs___] calls to
		WriteString[{before___, "WolframLanguageForJupyter-stdout", after___}, ourArgs___],
		in order to print in Jupyter *)
	Unprotect[WriteString];
	WriteString[{before___, "stdout", after___}, ourArgs___, opts:OptionsPattern[]] :=
		Block[
			{
				$inWriteString = True
			},
			If[
				loopState["WolframLanguageForJupyter-stdout"] =!= False,
				WriteString[{before, loopState["WolframLanguageForJupyter-stdout"], after}, ourArgs]
			];
		] /; !TrueQ[$inWriteString];
	Protect[WriteString];

(************************************
	versions of Quit and Exit that
		ask the Jupyter console
		to quit, if running under
		a Jupyter console
*************************************)
	
	Unprotect[Quit];
	Quit[ourArgs___] :=
		Block[
			{$inQuit = True},
			If[
				loopState["isCompleteRequestSent"],
				loopState["askExit"] = True;,
				Quit[ourArgs];
			];
		] /;
			(
				(!TrueQ[$inQuit]) &&
					(
						(Length[{ourArgs}] == 0) ||
							((Length[{ourArgs}] == 1) && IntegerQ[ourArgs])
					)
			);
	Protect[Quit];

	Unprotect[Exit];
	Exit[ourArgs___] :=
		Block[
			{$inExit = True},
			If[
				loopState["isCompleteRequestSent"],
				loopState["askExit"] = True;,
				Exit[ourArgs];
			];
		] /;
			(
				(!TrueQ[$inExit]) &&
					(
						(Length[{ourArgs}] == 0) ||
							((Length[{ourArgs}] == 1) && IntegerQ[ourArgs])
					)
			);
	Protect[Exit];

(************************************
	redirection utilities
*************************************)

	(* redirect Print to Jupyter *)
	redirectPrint[currentSourceFrame_, printText_] :=
		(* send a frame *)
		sendFrame[
			(* on the IO Publish socket *)
			ioPubSocket,
			(* create the frame *)
			createReplyFrame[
					(* using the current source frame *)
					currentSourceFrame,
					(* see https://jupyter-client.readthedocs.io/en/stable/messaging.html#streams-stdout-stderr-etc *)
					(* with a message type of "stream" *)
					"stream",
					(* and with message content that tells Jupyter what to Print, and to use stdout *)
					ExportString[
						Association[
								"name" -> "stdout",
								"text" -> printText
						],
						"JSON",
						"Compact" -> True
					],
					(* and without branching off *)
					False
			]
		];

	(* redirect messages to Jupyter *)
	redirectMessages[currentSourceFrame_, messageName_, messageText_, addNewline_, dropMessageName_:False] :=
		Module[
			{
				(* string forms of the arguments messageName and messageText *)
				messageNameString,
				messageTextString
			},
			(* generate string forms of the arguments *)
			messageNameString = ToString[HoldForm[messageName]];
			messageTextString = ToString[messageText];
			(* send a frame *)
			sendFrame[
				(* on the IO Publish socket *)
				ioPubSocket,
				(* create the frame *)
				createReplyFrame[
						(* using the current source frame *)
						currentSourceFrame,
						(* see https://jupyter-client.readthedocs.io/en/stable/messaging.html#execution-errors *)
						(* with a message type of "error" *)
						"error",
						(* and with appropriate message content *)
						ExportString[
							Association[
									(* use the provided message name here *)
									"ename" -> messageNameString,
									(* use the provided message text here *)
									"evalue" -> messageTextString,
									(* use the provided message name and message text here (unless dropMessageName) *)
									"traceback" ->
										{
											(* output the message in red *)
											StringJoin[
												"\033[0;31m",
												If[
													dropMessageName,
													(* use only the message text here if dropMessageName is True *)
													messageTextString,
													(* otherwise, combine the message name and message text *)
													ToString[System`ColonForm[HoldForm[messageName], messageText]]
												],
												(* if addNewline, add a newline *)
												If[addNewline, "\n", ""],
												"\033[0m"
											]
										}
							],
							"JSON",
							"Compact" -> True
						],
						(* and without branching off *)
						False
				]
			];
			(* ... and return an empty string to the Wolfram Language message system *)
			Return[""];
		];
	SetAttributes[redirectMessages, HoldAll];

(************************************
	utilities for splitting
		input by Wolfram Language
		expression
*************************************)

	(* start parsing the input, and return an Association for keeping track of said parse *)
	startParsingInput[codeStr_] :=
		Module[
			{
				(* an Association for keeping track of the parse containing:
					"LinesLeft" - the lines of input left to be processed,
					"ExpressionsParsed" - the number of expressions parsed out so far,
					"ExpressionString" - an expression string generated by a pass of the parser,
					"SyntaxError" - a flag for if the expression string contains a syntax error,
					"ParseDone" - a flag for if the parse is done *)
				parseTrackerInit
			},

			(* initialize parseTrackerInit *)
			parseTrackerInit = Association[];

			(* add the annotated lines left, and the defaults *)
			AssociateTo[
				parseTrackerInit,
				{
					"LinesLeft" -> StringSplit[StringJoin[" ", codeStr], "\r\n" | "\n"],
					"ExpressionsParsed" -> 0,
					"ExpressionString" -> " ",
					"SyntaxError" -> False,
					"ParseDone" -> False
				}
			];

			(* return the parse tracker *)
			Return[parseTrackerInit];
		];

	(* parse out an expression *)
	parseIntoExpr[tracker_] :=
		Module[
			{
				(* the parse tracker to be updated with the results of this parse *)
				newTracker,

				(* for storing the lines of input left to be processed, annotated with their line numbers *)
				annotatedLinesLeft,

				(* for storing the current line position when moving through annotatedLinesLeft *)
				linePos,

				(* for storing the result *)
				result,

				(* for storing the concatenation of some lines of input *)
				exprStr
			},

			(* initialize the parse tracker to be updated *)
			newTracker = tracker;

			(* if there are no lines of input left to be processed,
				set newTracker["ParseDone"] to True and return the updated tracker *)
			If[Length[newTracker["LinesLeft"]] == 0,
				newTracker["ParseDone"] = True;
				(* return the updated tracker *)
				Return[newTracker];
			];

			(* annotate the lines of input left to be processed with their line numbers *)
			annotatedLinesLeft = 
				Partition[
					Riffle[
						newTracker["LinesLeft"],
						Range[Length[newTracker["LinesLeft"]]]
					],
					2
				];

			(* start with a line position of 1 *)
			linePos = 1;
			result =
				(* fold until an expression is built, or there are no lines of input left *)
				Fold[
					(
						(* save the new line position *)
						linePos = Last[{##}][[2]] + 1;
						(* save the new expression string with a new line of input *)
						exprStr = StringJoin[First /@ {##}];
						(* if exprStr is syntactically correct, it represents a complete expression,
							and folding can be stopped *)
						If[SyntaxQ[exprStr],
							(* return the complete expression string *)
							Return[{exprStr, linePos, False}, Fold];,
							(* exprStr may be incomplete, keep going if possible *)
							{exprStr, linePos, True}
						]
					) &,
					(* starting value *)
					{"", -1, False},
					(* the annotated lines of input left to be processed *)
					annotatedLinesLeft
				];

			AssociateTo[
				newTracker,
				{
					(* discard the lines of input processed *)
					"LinesLeft" -> newTracker["LinesLeft"][[result[[2]];;]],
					(* increment ExpressionsParsed *)
					"ExpressionsParsed" -> newTracker["ExpressionsParsed"] + 1,
					(* save the result generated *)
					"ExpressionString" -> result[[1]],
					(* save the syntactic correctness of the result *)
					"SyntaxError" -> result[[3]]
				}
			];

			(* return the updated tracker *)
			Return[newTracker];
		];

(************************************
	main evaluation command
*************************************)

	(* evaluate input, and capture required information such as generated messages *)
	(* TODO: review other method: evaluate input through WSTP in another kernel *)
	simulatedEvaluate[codeStr_] :=
		Module[
			{
				(* for saving $Messages before changing it *)
				oldMessages,
				(* the stream used to capture generated messages *)
				stream,
				(* the string form of the generated messages, obtained from stream *)
				generatedMessages,

				(* for keeping track of parsing the input into separate expressions *)
				parseTracker,

				(* a raw evaluation result to be built, before Nulls have been removed *)
				rawEvaluationResult,

				(* for storing a single expression string *)
				exprStr,

				(* the result of evaluation *)
				evaluationResult,

				(* for storing final results *)
				result,

				(* the total result of the evaluation:
					an association containing
						the result of evaluation ("EvaluationResult"),
						indices of the output lines of the result ("EvaluationResultOutputLineIndices"),
						the total number of indices consumed by this evaluation ("ConsumedIndices"),
						generated messages ("GeneratedMessages"),
						if the input was one expression and wrapped with Interact[] ("InteractStatus")
				*)
				totalResult
			},

			(* create the association for the total result of the evaluation *)
			totalResult = Association[];

			(* save $Messages before overwrite *)
			oldMessages = $Messages;
			(* open stream to write messages into *)
			stream = OpenWrite[];

			(* clear the list of generated messages *)
			Unprotect[$MessageList]; $MessageList = {}; Protect[$MessageList];

			(* set $Messages to use the new stream *)
			$Messages = {stream};

			(* start the parse of the input *)
			parseTracker =
				startParsingInput[
					(* apply $PreRead to the input *)
					applyHook[$PreRead, codeStr]
				];

			(* initialize rawEvaluationResult to an empty list *)
			rawEvaluationResult = {};
			(* while the parse is not done, keep evaluating expressions in the input *)
			While[
				(
					parseTracker = parseIntoExpr[parseTracker];
					!parseTracker["ParseDone"]
				),

				(* save the current expression string *)
				exprStr = parseTracker["ExpressionString"];

				If[
					!parseTracker["SyntaxError"],
					(* increment $Line *)
					If[!IntegerQ[$Line], $Line = loopState["executionCount"] + parseTracker["ExpressionsParsed"] - 1];
					$Line++;
					(* set InString *)
					Unprotect[InString];
					InString[
							loopState["executionCount"] + parseTracker["ExpressionsParsed"] - 1
						] = exprStr;
					Protect[InString];
				];

				(* evaluate the expression string *)
				(* regarding Internal`AllowExceptions, we need to generate the results and messages that
					are expected when a user evaluation is interrupted by behavior such as an uncaught Throw
					statement, while making sure that the simulated evaluation loop is not interrupted by the
					same behavior; my hope is that we can achieve this by using Internal`AllowExceptions as
					essentially a version of CheckAll that does not silence messages such as Throw::nocatch *)
				result =
					Internal`AllowExceptions[
						ToExpression[
							exprStr,
							InputForm,
							uninteract
						]
					];

				If[
					!parseTracker["SyntaxError"],
					(* set the In[] for this expression *)
					Unprotect[In];
					Replace[
						ToExpression[exprStr, InputForm, Hold],
						Hold[held_] :> 
							SetDelayed[
								In[
									loopState["executionCount"] + parseTracker["ExpressionsParsed"] - 1
								],
								held
							]
					];
					Protect[In];
					(* apply $Post to the result *)
					result = applyHook[$Post, result];
					(* set the Out[] for this expression *)
					Unprotect[Out];
					Out[loopState["executionCount"] + parseTracker["ExpressionsParsed"] - 1] = result;
					Protect[Out];
					(* create the overall result with $PrePrint *)
					result = applyHook[$PrePrint, result];
					,
					(* syntax error *)
					result = $Failed;
				];

				(* save the result in rawEvaluationResult *)
				AppendTo[rawEvaluationResult, result];
			];

			(* add the Interact[] wrapper status of the input *)
			AssociateTo[
				totalResult,
				"InteractStatus" ->
					(
						(* if the input has no syntax errors,
							is made up of only one expression,
							and is wrapped with Interact[],
							mark "InteractStatus" as True
							*)
						parseTracker["ExpressionsParsed"] == 1 &&
							!parseTracker["SyntaxError"] &&
								(interactQ @ ToExpression[parseTracker["ExpressionString"], InputForm, Hold])
					)
			];

			(* evaluate the input from Jupyter, removing Nulls from the Output *)
			evaluationResult = DeleteCases[rawEvaluationResult, Null];

			(* preserve the locations of the output lines with respect to the Nulls *)
			AssociateTo[
				totalResult,
				"EvaluationResultOutputLineIndices" -> 
					(
						(loopState["executionCount"] - 1) + 
							Flatten[Position[rawEvaluationResult, Except[Null], {1}, Heads -> False]]
					)
			];

			(* restore $Messages *)
			$Messages = oldMessages;

			(* close the opened stream *)
			Close[stream];

			(* obtain generated messages *)
			If[
				FileExistsQ[stream[[1]]],
				generatedMessages = Import[stream[[1]], "String"];
				DeleteFile[stream[[1]]];,
				
				generatedMessages = "";
			];
			If[!StringQ[generatedMessages], generatedMessages = ""];

			(* add the total number of indices consumed by this evaluation *)
			AssociateTo[
				totalResult,
				"ConsumedIndices" -> 
					(* if parseTracker["SyntaxError"] is true, one less index was consumed *)
					If[
						parseTracker["SyntaxError"],
						parseTracker["ExpressionsParsed"] - 1,
						parseTracker["ExpressionsParsed"]
					]
			];

			(* add the result of the evaluation and any generated messages to totalResult *)
			AssociateTo[totalResult, {
				"EvaluationResult" -> evaluationResult,
				"GeneratedMessages" -> generatedMessages,
				"SyntaxError" -> TrueQ[parseTracker["SyntaxError"]]
			}];

			(* return totalResult *)
			Return[totalResult];
		];
	(* set simulatedEvaluate to not implicitly evaluate its arguments *)
	SetAttributes[simulatedEvaluate, HoldAll];

	(* Fix 4: 接受外部传入的 executionCount，使 Python 端计数与 WL 端 In[n]/Out[n] 保持同步 *)
	evaluateAndFormat[codeStr_String, externalCount_Integer: 0] :=
		Module[
			{
				totalResult,
				isSyntaxError, isAbort, isThrow, isError,
				ename, evalue, traceback,
				mimeBundles,
				capturedStdout, capturedStderr,
				executionCount
			},

			(* Fix 4: 如果 Python 传入了执行计数，优先使用它同步 In[n]/Out[n] *)
			If[externalCount > 0,
				loopState["executionCount"] = externalCount
			];

			(* 1. Initialize buffers *)
			loopState["capturedStdout"] = {};
			loopState["capturedStderr"] = {};
			loopState["LastMessages"] = {};

			(* 2. Set print and message formatters *)
			loopState["printFunction"] = (AppendTo[loopState["capturedStdout"], #1] &);

			messageFormatter[messageName_, messageText_] :=
				Module[
					{msgString},
					msgString = ToString[System`ColonForm[HoldForm[messageName], messageText]];
					AppendTo[loopState["LastMessages"], msgString];
					AppendTo[loopState["capturedStderr"], msgString];
					msgString
				];
			SetAttributes[messageFormatter, HoldAll];
			Internal`$MessageFormatter = messageFormatter;

			(* 3. Run evaluation *)
			totalResult = simulatedEvaluate[codeStr];

			(* 4. Cleanup formatters *)
			loopState["printFunction"] = False;
			Unset[messageFormatter];
			Unset[Internal`$MessageFormatter];

			(* 5. Check for execution errors *)
			isSyntaxError = TrueQ[totalResult["SyntaxError"]];
			isAbort = MemberQ[totalResult["EvaluationResult"], $Aborted];
			isThrow = AnyTrue[totalResult["EvaluationResult"], MatchQ[#, Hold[Throw[___]] | Hold[System`Throw[___]]] &];
			isError = isSyntaxError || isAbort || isThrow;

			executionCount = loopState["executionCount"];
			loopState["executionCount"] += totalResult["ConsumedIndices"];

			capturedStdout = StringJoin[loopState["capturedStdout"]];
			capturedStderr = loopState["capturedStderr"];

			If[isError,
				ename = Which[
					isSyntaxError, "SyntaxError",
					isAbort, "Abort",
					isThrow, "Throw",
					True, "Error"
				];
				evalue = Which[
					isSyntaxError,
						(* Fix 5: 使用 SyntaxLength 精确定位语法错误位置 *)
						Block[{pos, contextStr, baseMsg},
							pos = SyntaxLength[codeStr];
							baseMsg = Block[{t = StringTrim[totalResult["GeneratedMessages"]]},
								If[t === "\"\"" || t === "" || StringLength[t] == 0,
									If[ListQ[loopState["LastMessages"]] && Length[loopState["LastMessages"]] > 0,
										StringTrim[Last[loopState["LastMessages"]]],
										"Syntax error in expression."
									],
									t
								]
							];
							(* 若 SyntaxLength 给出有效的错误位置，附加位置提示 *)
							If[IntegerQ[pos] && pos >= 1 && pos <= StringLength[codeStr],
								contextStr = StringTake[
									codeStr,
									{Max[1, pos - 10], Min[StringLength[codeStr], pos + 10]}
								];
								StringJoin[baseMsg, " (near position ", ToString[pos], ": \"...", contextStr, "...\")"],
								baseMsg
							]
						],
					isAbort, "Evaluation aborted.",
					isThrow,
						Block[{trimmed = StringTrim[totalResult["GeneratedMessages"]]},
							If[trimmed === "\"\"" || trimmed === "" || StringLength[trimmed] == 0,
								If[ListQ[loopState["LastMessages"]] && Length[loopState["LastMessages"]] > 0,
									StringTrim[Last[loopState["LastMessages"]]],
									"Uncaught Throw returned to top level."
								],
								trimmed
							]
						],
					True, "Unknown evaluation error."
				];
				traceback = {
					StringJoin["\033[0;31m", ename, ": ", evalue, "\033[0m"]
				};

				Return[
					Association[
						"status" -> "error",
						"execution_count" -> executionCount,
						"ename" -> ename,
						"evalue" -> evalue,
						"traceback" -> traceback,
						"captured_stdout" -> capturedStdout,
						"captured_stderr" -> capturedStderr
					]
				];
			];

			(* 6. Format successful output *)
			(* Fix 2: 返回 mime_bundles 列表，每个非 Null 结果产生独立 bundle *)
			(* Python 侧：第 1 个发 execute_result，后续发 display_data *)
			If[Length[totalResult["EvaluationResultOutputLineIndices"]] == 0,
				Return[
					Association[
						"status" -> "ok",
						"execution_count" -> executionCount,
						"captured_stdout" -> capturedStdout,
						"captured_stderr" -> capturedStderr,
						"mime_bundles" -> {}
					]
				];
			];

			(* 为每个非 Null 求值结果生成独立的 mime bundle *)
			(* 避免对同一 item 调用 toMimeBundle 两次，使用 Block 缓存结果 *)
			mimeBundles = Map[
				Function[item,
					Block[{bundle = toMimeBundle[item]},
						Association[
							"data" -> bundle["data"],
							"metadata" -> bundle["metadata"]
						]
					]
				],
				totalResult["EvaluationResult"]
			];

			Return[
				Association[
					"status" -> "ok",
					"execution_count" -> executionCount,
					"captured_stdout" -> capturedStdout,
					"captured_stderr" -> capturedStderr,
					"mime_bundles" -> mimeBundles
				]
			];
		];

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotEvaluationUtilities *)
