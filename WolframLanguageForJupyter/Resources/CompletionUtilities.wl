(************************************************
				CompletionUtilities.wl
*************************************************
Description:
	Utilities for the aiding in the
		(auto-)completion of Wolfram Language
		code
Symbols defined:
	rewriteNamedCharacters
*************************************************)

(************************************
	Get[] guard
*************************************)

If[
	!TrueQ[WolframLanguageForJupyter`Private`$GotCompletionUtilities],
	
	WolframLanguageForJupyter`Private`$GotCompletionUtilities = True;

(************************************
	load required
		WolframLanguageForJupyter
		files
*************************************)

	Get[FileNameJoin[{DirectoryName[$InputFileName], "Initialization.wl"}]]; (* unicodeNamedCharactersReplacements,
																					verticalEllipsis *)

(************************************
	private symbols
*************************************)

	(* begin the private context for WolframLanguageForJupyter *)
	Begin["`Private`"];

(************************************
	utilities for rewriting
		Wolfram Language code
*************************************)

	(* rewrite names (in a code string) into named characters *)
	rewriteNamedCharacters[codeToAnalyze_?StringQ] :=
		Module[
			{codeUsingFullReplacements},
			codeUsingFullReplacements =
				StringReplace[
					codeToAnalyze,
					Normal @ unicodeNamedCharactersReplacements
				];
			If[
				StringCount[
					codeUsingFullReplacements,
					verticalEllipsis | "\\["
				] != 1,
				Return[{codeUsingFullReplacements}];
			];
			Return[
				Flatten[
					StringCases[
						codeUsingFullReplacements,
						before___ ~~ name : ((verticalEllipsis | "\\[") ~~ rest__ ~~ EndOfString) :>
							(
								(StringJoin[before, #1] &) /@
									Values[
										KeySelect[
											unicodeNamedCharactersReplacements,
											StringMatchQ[#1, name ~~ ___] &
										]
									]
							)
					]
				]
			];
		];

	getWordBoundaries[code_String, cursorPos_Integer] :=
		Module[{chars = Characters[code], len = StringLength[code], 
				start = cursorPos, end = cursorPos + 1, char},
			If[cursorPos <= 0, Return[{1, 1}]];
			While[start > 0,
				char = chars[[start]];
				If[StringMatchQ[char, LetterCharacter | DigitCharacter | "$" | "`"],
					start = start - 1;
				,
					If[char === "[" && start > 1 && chars[[start - 1]] === "\\",
						start = start - 2;
						Break[];
					];
					If[char === verticalEllipsis,
						start = start - 1;
						Break[];
					];
					Break[];
				]
			];
			start = start + 1;
			While[end <= len,
				char = chars[[end]];
				If[StringMatchQ[char, LetterCharacter | DigitCharacter | "$" | "`"],
					end = end + 1;
				,
					Break[];
				]
			];
			{start, end}
		];

	findEnclosingFunction[code_String] :=
		Module[{chars = Characters[code], len = StringLength[code], 
				bracketStack = {}, i, char, matching, symbolChars, funcName = ""},
			i = len;
			While[i >= 1,
				char = chars[[i]];
				If[MemberQ[{"]", "}", ")"}, char],
					AppendTo[bracketStack, char];
				,
					If[MemberQ[{"[", "{", "("}, char],
						matching = Replace[char, {"[" -> "]", "{" -> "}", "(" -> ")"}];
						If[Length[bracketStack] > 0 && Last[bracketStack] === matching,
							bracketStack = Delete[bracketStack, -1];
						,
							If[char === "[",
								symbolChars = {};
								i = i - 1;
								While[i >= 1 && (StringMatchQ[chars[[i]], LetterCharacter | DigitCharacter | "$" | "`"]),
									PrependTo[symbolChars, chars[[i]]];
									i = i - 1;
								];
								If[Length[symbolChars] > 0,
									funcName = StringJoin[symbolChars];
								];
								Break[];
							]
						]
					]
				];
				i = i - 1;
			];
			funcName
		];

	getOptionCompletions[funcStr_String, prefix_String] :=
		Module[{funcSymbol, opts, optNames},
			If[!NameQ[funcStr] && !NameQ["System`" <> funcStr], Return[{}]];
			funcSymbol = Symbol[If[NameQ[funcStr], funcStr, "System`" <> funcStr]];
			opts = Options[funcSymbol];
			If[opts === {}, Return[{}]];
			optNames = Map[SymbolName, Keys[opts]];
			Select[optNames, StringMatchQ[#, prefix ~~ ___, IgnoreCase -> True] &]
		];

	(* get code completion list *)
	getCompletions[code_String, cursorPos_Integer] := Module[
		{len = StringLength[code], boundaries, start, end, prefix, 
		namedPrefix, symbolMatches, optionMatches, combinedMatches, resultMatches,
		enclosingFunc = ""},
		
		If[cursorPos > len, Return[
			Association[
				"matches" -> {},
				"cursor_start" -> len,
				"cursor_end" -> len
			]
		]];
		If[cursorPos <= 0,
			Return[
				Association[
					"matches" -> {},
					"cursor_start" -> 0,
					"cursor_end" -> 0
				]
			];
		];
		
		boundaries = getWordBoundaries[code, cursorPos];
		start = boundaries[[1]];
		end = boundaries[[2]];
		
		prefix = StringTake[code, {start, cursorPos}];
		
		(* Check if prefix is a valid symbol start (cannot start with a digit) *)
		If[StringLength[prefix] > 0,
			If[!StringMatchQ[StringTake[prefix, 1], LetterCharacter | "$" | "`" | "\\" | verticalEllipsis],
				(* Reset to empty prefix *)
				prefix = "";
				start = cursorPos + 1;
				end = cursorPos + 1;
			]
		];
		
		(* 1. Match Named Character prefix *)
		namedPrefix = StringCases[
			prefix,
			(p : (("\\[" | verticalEllipsis) ~~ (WordCharacter | "$")...)) ~~ EndOfString :> p
		];
		
		If[Length[namedPrefix] > 0,
			namedPrefix = namedPrefix[[1]];
			Return[
				Association[
					"matches" -> Select[rewriteNamedCharacters[namedPrefix], (!containsPUAQ[#1])&],
					"cursor_start" -> start - 1,
					"cursor_end" -> end - 1
				]
			];
		];
		
		(* 2. Find enclosing function for options completion *)
		enclosingFunc = findEnclosingFunction[StringTake[code, {1, start - 1}]];
		
		(* 3. Get matches *)
		optionMatches = {};
		If[enclosingFunc =!= "" && StringLength[prefix] > 0,
			optionMatches = getOptionCompletions[enclosingFunc, prefix];
		];
		
		symbolMatches = {};
		If[StringLength[prefix] > 0,
			Block[{pos, lastPos, contextPart, symbolPart, firstChar, queryChar, queryPrefix},
				pos = StringPosition[prefix, "`"];
				If[Length[pos] > 0,
					lastPos = Last[Last[pos]];
					contextPart = StringTake[prefix, lastPos];
					symbolPart = StringDrop[prefix, lastPos];
				,
					contextPart = "";
					symbolPart = prefix;
				];
				
				If[StringLength[symbolPart] > 0,
					firstChar = StringTake[symbolPart, 1];
					queryChar = If[StringMatchQ[firstChar, LetterCharacter], ToUpperCase[firstChar], firstChar];
					queryPrefix = contextPart <> queryChar;
				,
					queryPrefix = contextPart;
				];
				
				symbolMatches = Select[
					Names[queryPrefix ~~ ___], 
					(StringMatchQ[#, prefix ~~ ___, IgnoreCase -> True] && 
					 !StringContainsQ[#, "Private`"] && 
					 !StringContainsQ[#, "WolframLanguageForJupyter`"]) &
				];
			];
		];
		
		(* Combine and sort: options first, then shorter names *)
		combinedMatches = Join[optionMatches, symbolMatches];
		resultMatches = DeleteDuplicates[combinedMatches];
		resultMatches = SortBy[resultMatches, {If[MemberQ[optionMatches, #], 0, 1] &, StringLength}];
		
		Return[
			Association[
				"matches" -> Take[resultMatches, UpTo[100]],
				"cursor_start" -> start - 1,
				"cursor_end" -> end - 1
			]
		];
	];

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotCompletionUtilities *)
