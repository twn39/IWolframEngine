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

	(* get code completion list *)
	getCompletions[codeStr_String] := Module[
		{namedPrefix, symbolPrefix, symbolMatches, prefixMatch},
		
		(* 1. Match Named Character prefix *)
		namedPrefix = StringCases[
			codeStr,
			(prefix : (("\\[" | verticalEllipsis) ~~ (WordCharacter | "$")...)) ~~ EndOfString :> prefix
		];
		
		If[Length[namedPrefix] > 0,
			namedPrefix = namedPrefix[[1]];
			Return[
				Association[
					"matches" -> Select[rewriteNamedCharacters[namedPrefix], (!containsPUAQ[#1])&],
					"cursor_start" -> StringLength[codeStr] - StringLength[namedPrefix],
					"cursor_end" -> StringLength[codeStr]
				]
			];
		];
		
		(* 2. Match standard symbol prefix *)
		symbolPrefix = StringCases[
			codeStr,
			(prefix : ((LetterCharacter | "$" | "`") ~~ (WordCharacter | "$" | "`")...)) ~~ EndOfString :> prefix
		];
		
		If[Length[symbolPrefix] > 0,
			symbolPrefix = symbolPrefix[[1]];
			symbolMatches = Names[symbolPrefix ~~ ___];
			Return[
				Association[
					"matches" -> Take[symbolMatches, UpTo[100]],
					"cursor_start" -> StringLength[codeStr] - StringLength[symbolPrefix],
					"cursor_end" -> StringLength[codeStr]
				]
			];
		];
		
		(* 3. Fallback *)
		Return[
			Association[
				"matches" -> {},
				"cursor_start" -> StringLength[codeStr],
				"cursor_end" -> StringLength[codeStr]
			]
		];
	];

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotCompletionUtilities *)
