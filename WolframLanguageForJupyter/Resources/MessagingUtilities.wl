(************************************************
				MessagingUtilities.wl
*************************************************
Description:
	Higher-level utilities for sending
		and receiving messages from Jupyter
Symbols defined:
	getFrameAssoc,
	createReplyFrame
*************************************************)

(************************************
	Get[] guard
*************************************)

If[
	!TrueQ[WolframLanguageForJupyter`Private`$GotMessagingUtilities],
	
	WolframLanguageForJupyter`Private`$GotMessagingUtilities = True;

(************************************
	load required
		WolframLanguageForJupyter
		files
*************************************)

	Get[FileNameJoin[{DirectoryName[$InputFileName], "SocketUtilities.wl"}]]; (* hmac *)

(************************************
	private symbols
*************************************)

	(* begin the private context for WolframLanguageForJupyter *)
	Begin["`Private`"];

(************************************
	utilities for reading in, and
		writing out, message
		frames
*************************************)

	(* transform received frame into a structured Association *)
	(* Robust linear-time parser for concatenated Jupyter message parts *)
	parseJupyterMessage[frameStr_String] := Module[
		{delimPos, ident, signature, rest, jsonObjects, jsonStartPos, chars, len, 
		 bracketDepth, inString, escaped, i, c, jsonStart, jsonString},
		
		delimPos = StringPosition[frameStr, "<IDS|MSG>"];
		If[Length[delimPos] == 0, Return[$Failed]];
		delimPos = delimPos[[1]];
		
		ident = StringTake[frameStr, delimPos[[1]] - 1];
		rest = StringDrop[frameStr, delimPos[[2]]];
		
		jsonStartPos = StringPosition[rest, "{"];
		If[Length[jsonStartPos] == 0, Return[$Failed]];
		jsonStartPos = jsonStartPos[[1, 1]];
		
		signature = StringTake[rest, jsonStartPos - 1];
		rest = StringDrop[rest, jsonStartPos - 1];
		
		chars = Characters[rest];
		len = Length[chars];
		jsonObjects = {};
		i = 1;
		
		Do[
			While[i <= len && chars[[i]] =!= "{", i++];
			If[i > len, Return[$Failed]];
			
			jsonStart = i;
			bracketDepth = 0;
			inString = False;
			escaped = False;
			
			While[i <= len,
				c = chars[[i]];
				If[inString,
					If[escaped,
						escaped = False;,
						If[c === "\\",
							escaped = True;,
							If[c === "\"", inString = False;]
						]
					];,
					If[c === "\"",
						inString = True;
						escaped = False;,
						If[c === "{",
							bracketDepth++;,
							If[c === "}",
								bracketDepth--;
								If[bracketDepth == 0,
									jsonString = StringJoin[chars[[jsonStart ;; i]]];
									AppendTo[jsonObjects, jsonString];
									i++;
									Break[];
								];
							]
						]
					]
				];
				i++;
			];
			If[bracketDepth > 0, Return[$Failed]];,
			{4}
		];
		
		If[Length[jsonObjects] < 4, Return[$Failed]];
		
		Return[<|
			"ident" -> ident,
			"signature" -> signature,
			"header" -> jsonObjects[[1]],
			"pheader" -> jsonObjects[[2]],
			"metadata" -> jsonObjects[[3]],
			"content" -> jsonObjects[[4]]
		|>];
	];

	(* transform received frame into a structured Association *)
	getFrameAssoc[baFrame_ByteArray] :=
		Module[
			{
				frameStr,
				parsed,
				identLen
			},

			(* set frameStr to the string form of the byte array of the received frame *)
			frameStr = Quiet[ByteArrayToString[baFrame]];

			parsed = parseJupyterMessage[frameStr];
			If[FailureQ[parsed], Return[$Failed]];

			identLen = StringLength[parsed["ident"]];

			Return[
				Association[
					"ident" -> baFrame[[;;identLen]],
					"header" -> Association[ImportByteArray[StringToByteArray[parsed["header"]], "JSON"]],
					"content" -> Association[ImportByteArray[StringToByteArray[parsed["content"]], "JSON"]]
				]
			];
		];

	(* generate a reply message frame from using a source message frame, replyType, and replyContent *)
	createReplyFrame[
			(* the source frame to use, after it has been ran through getFrameAssoc *)
			sourceFrame_Association,
			(* the message type to be used for the reply message frame *)
			replyType_String,
			(* the content to be used for the reply message frame *)
			replyContent : (_String | _ByteArray),
			(* whether to list sourceFrame as a parent for the reply message frame *)
			branchOff:(True|False)
		] := 
			Module[
				{
					(* for storing the header and content of the source message frame *)
					header, content,

					(* the association for the generated reply message frame *)
					result
				},

				(* save the header and content of the source message frame *)
				header = sourceFrame["header"];
				content = sourceFrame["content"];

				(* build reply message *)
				(* see https://jupyter-client.readthedocs.io/en/stable/messaging.html for why the following are set as they are *)
				result = Association[
							"ident" -> If[KeyExistsQ[sourceFrame, "ident"], sourceFrame["ident"], ByteArray[{0, 0, 0, 0, 0}]],
							"idsmsg" -> "<IDS|MSG>",
							"header" -> ExportString[
											Append[
												header,
												{"date" -> DateString["ISODateTime"], "msg_type" -> replyType, "msg_id" -> StringInsert[StringReplace[CreateUUID[], "-" -> ""], "-", 9]}
											],
											"JSON",
											"Compact" -> True
										],
							"pheader" -> If[branchOff, "{}", ExportString[header, "JSON", "Compact" -> True]],
							"metadata" -> ExportString[
											{"text/html" -> {}},
											"JSON",
											"Compact" -> True
										],
							"content" -> replyContent
						];

				(* generate the signature of the reply message *)
				AssociateTo[
					result,
					"signature" -> 
						hmac[
							keyString, 
							StringJoin[
								result["header"],
								result["pheader"],
								result["metadata"],
								If[StringQ[result["content"]], result["content"], ByteArrayToString[result["content"]]]
							]
						]
				];

				(* return the built reply message frame *)
				Return[result];
			];

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotMessagingUtilities *)
