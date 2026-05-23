(************************************************
				OutputHandlingUtilities.wl
*************************************************
Description:
	Utilities for handling the result
		of Wolfram Language expressions
		so that, as outputs, they are
		reasonably displayed in Jupyter
		notebooks
Symbols defined:
	textQ,
	toText,
	toOutTextHTML,
	toImageData,
	toOutImageHTML
*************************************************)

(************************************
	Get[] guard
*************************************)

If[
	!TrueQ[WolframLanguageForJupyter`Private`$GotOutputHandlingUtilities],
	
	WolframLanguageForJupyter`Private`$GotOutputHandlingUtilities = True;

(************************************
	load required
		WolframLanguageForJupyter
		files
*************************************)

	Get[FileNameJoin[{DirectoryName[$InputFileName], "Initialization.wl"}]]; (* $canUseFrontEnd, $outputSetToTeXForm,
																					$outputSetToTraditionalForm,
																					$trueFormatType, $truePageWidth,
																					failedInBase64 *)

(************************************
	private symbols
*************************************)

	(* begin the private context for WolframLanguageForJupyter *)
	Begin["`Private`"];

(************************************
	helper utility for converting
		an expression into a
		textual form
*************************************)

	(* convert an expression into a textual form,
		using as much of the options already set for $Output as possible for ToString *)
	(* NOTE: toOutTextHTML used to call toStringUsingOutput *)
	toStringUsingOutput[expr_] :=
		ToString[
			expr,
			Sequence @@
				Cases[
					Options[$Output],
					Verbatim[Rule][opt_, val_] /;
						MemberQ[
							Keys[Options[ToString]],
							opt
						]
				]
		];

(************************************
	helper utility for determining
		if a result should be
		displayed as text or an image
*************************************)

	(* check if a string contains any private use area characters *)
	containsPUAQ[str_] :=
		AnyTrue[
			ToCharacterCode[str, "Unicode"],
			(57344 <= #1 <= 63743 || 983040 <= #1 <= 1048575 || 1048576 <= #1 <= 1114111) &
		];

(************************************
	utility for determining if a
		result should be displayed
		as text or an image
*************************************)

	(* determine if a result does not depend on any Wolfram Language frontend functionality,
		such that it should be displayed as text *)
	textQ[expr_] := Module[
		{
			(* the head of expr *)
			exprHead,

			(* pattern objects *)
			pObjects
		}, 

		(* if we cannot use the frontend, use text *)
		If[
			!$canUseFrontEnd,
			Return[True];
		];

		(* save the head of the expression *)
		exprHead = Head[expr];

		(* if the expression is wrapped with InputForm or OutputForm,
			automatically format as text *)
		If[exprHead === InputForm || exprHead === OutputForm,
			Return[True]
		];

		(* if the FormatType of $Output is set to TeXForm, or if the expression is wrapped with TeXForm,
			and the expression has an acceptable textual form, format as text *)
		If[($outputSetToTeXForm || exprHead == TeXForm) && !containsPUAQ[ToString[expr]],
			Return[True];
		];

		(* if the FormatType of $Output is set to TraditionalForm,
			or if the expression is wrapped with TraditionalForm,
			do not use text *)
		If[$outputSetToTraditionalForm || exprHead === TraditionalForm,
			Return[False]
		];

		(* breakdown expr into atomic objects organized by their Head *)
		pObjects = 
			GroupBy[
				Complement[
					Quiet[Cases[
						expr, 
						elem_ /; (Depth[Unevaluated[elem]] == 1) -> Hold[elem], 
						{0, Infinity}, 
						Heads -> True
					]],
					(* these symbols are fine *)
					{Hold[List], Hold[Association]}
				],
				(
					Replace[
						#1,
						Hold[elem_] :> Head[Unevaluated[elem]]
					]
				) &
			];

	   	(* if expr just contains atomic objects of the types listed above, return True *)
		If[
			ContainsOnly[Keys[pObjects], {Integer, Real}],
			Return[True];
	   	];

	   	(* if expr just contains atomic objects of the types listed above, along with some symbols,
	   		return True only if the symbols have no attached rules *)
		If[
			ContainsOnly[Keys[pObjects], {Integer, Real, String, Symbol}],
	   		Return[
				AllTrue[
						Lookup[pObjects, String, {}], 
						(!containsPUAQ[ReleaseHold[#1]]) &
					] &&
		   			AllTrue[
		   				Lookup[pObjects, Symbol, {}], 
		   				(
							Replace[
								#1,
								Hold[elem_] :> ToString[Definition[elem]]
							] === "Null"
		   				) &
		   			]
	   		];
	   	];

	   	(* otherwise, no, the result should not be displayed as text *)
	   	Return[False];
	];

(************************************
	utilities for generating
		HTML for displaying
		results as text and images
*************************************)

	(* generate the textual form of a result using a given page width *)
	(* NOTE: the OutputForm (which ToString uses) of any expressions wrapped with, say, InputForm should
		be identical to the string result of an InputForm-wrapped expression itself *)
	toText[result_, pageWidth_] :=
		ToString[
			(* make sure to apply $trueFormatType to the result if the result is not already headed by TeXForm *)
			If[
				Head[result] === TeXForm,
				result,
				$trueFormatType[result]
			],
			(* also, use the given page width *)
			PageWidth -> pageWidth
		];
	(* generate the textual form of a result using the current PageWidth setting for $Output *)
	toText[result_] := toText[result, $truePageWidth];

	(* generate HTML for the textual form of a result *)
	toOutTextHTML[result_] := 
		Module[
			{
				(* if the result should be marked as TeX *)
				isTeX
			},
			(* check if the result should be marked as TeX *)
			isTeX = ((Head[result] === TeXForm) || ($outputSetToTeXForm));
			Return[
				StringJoin[

					(* mark this result as preformatted only if it isn't TeX *)
					If[
						!isTeX,
						{
							(* preformatted *)
							"<pre style=\"",
							(* use Courier *)
							StringJoin[{"&#", ToString[#1], ";"} & /@ ToCharacterCode["font-family: \"Courier New\",Courier,monospace;", "Unicode"]], 
							"\">"
						},
						{}
					],

					(* mark the text as TeX, if is TeX *)
					If[isTeX, "&#36;&#36;", ""],

					(* the textual form of the result *)
					({"&#", ToString[#1], ";"} & /@ 
						ToCharacterCode[
							If[
								isTeX,
								(* if the result is TeX, do not allow line breaks *)
								toText[result, Infinity],
								(* otherwise, just call toText *)
								toText[result]
							],
							"Unicode"
						]),

					(* mark the text as TeX, if is TeX *)
					If[isTeX, "&#36;&#36;", ""],

					(* mark this result as preformatted only if it isn't TeX *)
					If[
						!isTeX,
						{
							(* end the element *)
							"</pre>"
						},
						{}
					]
				]
			];
		];

	(* generate a byte array of image data for the rasterized form of a result *)
	(* dpi: image resolution; default 144 for HiDPI/Retina screen support (2x logical pixels) *)
	toImageData[result_, dpi_:144] :=
		Module[
			{
				(* the preprocessed form of a result *)
				preprocessedForm
			},
			(* preprocess the result *)
			If[
				Head[result] === Manipulate,
				preprocessedForm = result;
				,
				(* rasterize at specified DPI for crisp output on HiDPI screens *)
				preprocessedForm = Rasterize[result, ImageResolution -> dpi];
			];
			(* if the preprocessing failed, return $Failed *)
			If[
				FailureQ[preprocessedForm],
				Return[$Failed];
			];
			(* now return preprocessedForm as a byte array corresponding to the PNG format *)
			Return[
				ExportByteArray[
					preprocessedForm,
					"PNG"
				]
			];
		];

	(* generate an SVG string for the result; returns $Failed if the export fails *)
	(* SVG is a lossless vector format, infinitely scalable on any screen *)
	toSVGString[expr_] :=
		Module[
			{svgStr},
			svgStr = Quiet[ExportString[expr, "SVG"]];
			If[StringQ[svgStr] && StringLength[svgStr] > 0,
				(* Strip XML declaration if present to ensure proper inline SVG rendering in notebooks *)
				If[StringStartsQ[svgStr, "<?xml"],
					svgStr = StringReplace[svgStr, StartOfString ~~ "<?xml" ~~ Shortest[___] ~~ "?>" ~~ (Whitespace | "") -> ""]
				];
				svgStr,
				$Failed
			]
		];

	(* determine if an expression is a Wolfram graphics object that should be rendered visually *)
	(* This check is INDEPENDENT of $canUseFrontEnd, because Rasterize and ExportString[..., "SVG"]
	   work correctly in headless Wolfram Engine without a frontend. *)
	graphicsQ[expr_] :=
		MemberQ[
			{
				Graphics, Graphics3D, Graph, Image, GeoGraphics,
				GeometricScene, ContourGraphics, DensityGraphics,
				SurfaceGraphics, GraphicsArray, GraphicsGrid, GraphicsRow, GraphicsColumn
			},
			Head[expr]
		];

	(* determine if an expression has a mathematical head for automatic LaTeX rendering *)
	isMathExprQ[expr_] :=
		With[{h = Head[expr]},
			MemberQ[
				{
					Plus, Times, Power, Rational, Log, Log10, Log2, Exp, Sin, Cos, Tan, Cot, Sec, Csc,
					ArcSin, ArcCos, ArcTan, ArcCot, Sinh, Cosh, Tanh, Integrate, System`D, Derivative,
					MatrixForm, SeriesData, Limit, Sum, Product, Solve, Reduce, Equal, Unequal,
					Greater, Less, GreaterEqual, LessEqual
				},
				h
			] || (
				MemberQ[{Hold, HoldForm, Defer, HoldPattern}, h] &&
				Length[expr] >= 1 &&
				isMathExprQ[First[expr]]
			)
		];

	(* clean up Wolfram-specific LaTeX syntax into web-safe MathJax strings *)
	sanitizeLaTeX[latexStr_String] :=
		Module[
			{cleanStr = StringTrim[latexStr]},
			cleanStr = StringReplace[cleanStr, {
				"\\text{d}" -> "\\mathrm{d}"
			}];
			cleanStr
		];

	(* generate HTML for the rasterized form of a result *)
	toOutImageHTML[result_] := 
		Module[
			{
				(* the rasterization of result *)
				imageData,
				(* the rasterization of result in base 64 *)
				imageInBase64,
				(* PNG image dimensions for size styling *)
				pngWidth, pngHeight,
				widthAttr = "", heightAttr = ""
			},

			(* rasterize the result *)
			imageData =
				toImageData[
					$trueFormatType[result]
				];
			If[
				!FailureQ[imageData],
				(* if the rasterization did not fail, convert it to base 64 *)
				imageInBase64 = BaseEncode[imageData];
				Block[
					{parsedImg},
					parsedImg = Quiet[ImportByteArray[imageData, "PNG"]];
					If[Head[parsedImg] === Image,
						{pngWidth, pngHeight} = ImageDimensions[parsedImg];
						If[pngWidth > 0 && pngHeight > 0,
							widthAttr = StringJoin[" width=\"", ToString[Ceiling[pngWidth / 2]], "\""];
							heightAttr = StringJoin[" height=\"", ToString[Ceiling[pngHeight / 2]], "\""];
						];
					];
				];
				,
				(* if the rasterization did fail, try to rasterize result with Shallow *)
				imageData =
					toImageData[
						$trueFormatType[Shallow[result]]
					];
				If[
					!FailureQ[imageData],
					(* if the rasterization did not fail, convert it to base 64 *)
					imageInBase64 = BaseEncode[imageData];
					Block[
						{parsedImg},
						parsedImg = Quiet[ImportByteArray[imageData, "PNG"]];
						If[Head[parsedImg] === Image,
							{pngWidth, pngHeight} = ImageDimensions[parsedImg];
							If[pngWidth > 0 && pngHeight > 0,
								widthAttr = StringJoin[" width=\"", ToString[Ceiling[pngWidth / 2]], "\""];
								heightAttr = StringJoin[" height=\"", ToString[Ceiling[pngHeight / 2]], "\""];
							];
						];
					];
					,
					(* if the rasterization did fail, try to rasterize $Failed *)
					imageData =
						toImageData[
							$trueFormatType[$Failed]
						];
					If[
						!FailureQ[imageData],
						(* if the rasterization did not fail, convert it to base 64 *)
						imageInBase64 = BaseEncode[imageData];
						Block[
							{parsedImg},
							parsedImg = Quiet[ImportByteArray[imageData, "PNG"]];
							If[Head[parsedImg] === Image,
								{pngWidth, pngHeight} = ImageDimensions[parsedImg];
								If[pngWidth > 0 && pngHeight > 0,
									widthAttr = StringJoin[" width=\"", ToString[Ceiling[pngWidth / 2]], "\""];
									heightAttr = StringJoin[" height=\"", ToString[Ceiling[pngHeight / 2]], "\""];
								];
							];
						];
						,
						(* if the rasterization did fail, use a hard-coded base64 rasterization of $Failed *)
						imageInBase64 = failedInBase64;
					];
				];
			];

			(* return HTML for the rasterized form of result *)
			Return[
				StringJoin[
					(* display a inlined PNG image encoded in base64 *)
					"<img alt=\"Output\" src=\"data:image/png;base64,",
					(* the rasterized form of the result, converted to base64 *)
					imageInBase64,
					(* end the element with width and height attributes *)
					"\"", widthAttr, heightAttr, ">"
				]
			]
		];

	(* check if the expression represents a structured table *)
	isTableQ[expr_] := MemberQ[{Dataset, TableForm, Grid}, Head[expr]];

	(* sanitize text content for HTML output *)
	escapeHTML[str_String] := StringReplace[str, {
		"&" -> "&amp;",
		"<" -> "&lt;",
		">" -> "&gt;",
		"\"" -> "&quot;",
		"'" -> "&#x27;"
	}];
	escapeHTML[expr_] := escapeHTML[ToString[expr]];

	(* format generic cell values dynamically *)
	formatCell[expr_] := Which[
		StringQ[expr],
		escapeHTML[expr],
		
		IntegerQ[expr] || Head[expr] === Real,
		ToString[expr],
		
		isMathExprQ[expr],
		StringJoin["$", sanitizeLaTeX[toText[TeXForm[expr], Infinity]], "$"],
		
		graphicsQ[expr],
		toHTML[expr],
		
		isTableQ[expr],
		toHTMLTable[expr],
		
		True,
		escapeHTML[toText[expr]]
	];

	(* format grid cells, leaving span control tokens untouched *)
	formatGridCell[expr_] := If[
		MemberQ[{SpanFromLeft, SpanFromAbove, SpanFromBoth}, expr],
		expr,
		formatCell[expr]
	];

	(* beautify and wrap raw HTML tables with scrolling container and styles *)
	beautifyHTMLTable[html_String] := StringJoin[
		"<div class=\"wolfram-table-container\"><style>",
		"
.wolfram-table-container { overflow-x: auto; margin: 12px 0; }
table.wolfram-table { border-collapse: collapse; font-family: var(--jp-content-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif); font-size: var(--jp-content-font-size1, 14px); color: var(--jp-content-font-color1, black); border: 1px solid var(--jp-border-color1, #dcdcdc); text-align: left; min-width: 200px; background-color: var(--jp-layout-color1, #ffffff); box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 4px; }
table.wolfram-table th { background-color: var(--jp-layout-color2, #f5f5f5); color: var(--jp-content-font-color1, black); font-weight: 600; padding: 8px 12px; border: 1px solid var(--jp-border-color1, #dcdcdc); font-size: calc(var(--jp-content-font-size1, 14px) - 1px); }
table.wolfram-table td { padding: 8px 12px; border: 1px solid var(--jp-border-color2, #e0e0e0); vertical-align: middle; }
table.wolfram-table tbody tr:nth-child(even) { background-color: var(--jp-layout-color2, #fafafa); }
table.wolfram-table tbody tr:hover { background-color: var(--jp-layout-color3, #f0f0f0); }
",
		"</style>",
		If[
			StringContainsQ[html, "class=\"wolfram-table\""],
			html,
			StringReplace[html, {
				"<table class=\"grid\">" -> "<table class=\"wolfram-table\">",
				"<table>" -> "<table class=\"wolfram-table\">"
			}]
		],
		"</div>"
	];

	(* pagination parameters for large tables *)
	$maxRowsToDisplay = 60;
	$headRowsToDisplay = 30;
	$tailRowsToDisplay = 30;

	(* format small muted metadata footer showing dimensions *)
	formatDimensionFooter[summary_String] := StringJoin[
		"<div style=\"font-size: 11px; color: var(--jp-ui-font-color3, #888888); margin-top: 4px; font-family: var(--jp-content-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif);\">",
		"[", summary, "]",
		"</div>"
	];

	(* table serializers for Dataset, TableForm, and Grid *)
	toHTMLTable[expr_Dataset] := Module[
		{data, html},
		data = Normal[expr];
		html = Which[
			ListQ[data] && Length[data] > 0 && AllTrue[data, AssociationQ],
			Module[{headers, tableHtml, row, val, numCols, isTruncated, headRows, tailRows},
				headers = DeleteDuplicates[Flatten[Keys /@ data]];
				numCols = Length[headers] + 1;
				isTruncated = Length[data] > $maxRowsToDisplay;
				
				tableHtml = "<table class=\"wolfram-table\"><thead><tr><th></th>";
				Do[
					tableHtml = tableHtml <> "<th>" <> formatCell[h] <> "</th>",
					{h, headers}
				];
				tableHtml = tableHtml <> "</tr></thead><tbody>";
				
				If[isTruncated,
					headRows = Take[data, $headRowsToDisplay];
					tailRows = Take[data, -$tailRowsToDisplay];
					
					Do[
						row = headRows[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[i] <> "</td>";
						Do[
							val = Lookup[row, key, ""];
							tableHtml = tableHtml <> "<td>" <> formatCell[val] <> "</td>",
							{key, headers}
						];
						tableHtml = tableHtml <> "</tr>",
						{i, 1, Length[headRows]}
					];
					
					tableHtml = tableHtml <> "<tr><td colspan=\"" <> ToString[numCols] <> "\" style=\"text-align: center; color: var(--jp-ui-font-color3, #888888); font-weight: bold; background-color: var(--jp-layout-color1, #ffffff);\">...</td></tr>";
					
					Do[
						row = tailRows[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[Length[data] - Length[tailRows] + i] <> "</td>";
						Do[
							val = Lookup[row, key, ""];
							tableHtml = tableHtml <> "<td>" <> formatCell[val] <> "</td>",
							{key, headers}
						];
						tableHtml = tableHtml <> "</tr>",
						{i, 1, Length[tailRows]}
					];
					,
					Do[
						row = data[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[i] <> "</td>";
						Do[
							val = Lookup[row, key, ""];
							tableHtml = tableHtml <> "<td>" <> formatCell[val] <> "</td>",
							{key, headers}
						];
						tableHtml = tableHtml <> "</tr>",
						{i, 1, Length[data]}
					];
				];
				
				tableHtml = tableHtml <> "</tbody></table>";
				tableHtml = tableHtml <> formatDimensionFooter[ToString[Length[data]] <> " rows x " <> ToString[Length[headers]] <> " columns"];
				tableHtml
			],
			
			AssociationQ[data],
			Module[{tableHtml, key, val, keys, isTruncated, headKeys, tailKeys},
				keys = Keys[data];
				isTruncated = Length[keys] > $maxRowsToDisplay;
				tableHtml = "<table class=\"wolfram-table\"><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>";
				
				If[isTruncated,
					headKeys = Take[keys, $headRowsToDisplay];
					tailKeys = Take[keys, -$tailRowsToDisplay];
					
					Do[
						key = headKeys[[i]];
						val = data[key];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[key] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[headKeys]}
					];
					
					tableHtml = tableHtml <> "<tr><td colspan=\"2\" style=\"text-align: center; color: var(--jp-ui-font-color3, #888888); font-weight: bold; background-color: var(--jp-layout-color1, #ffffff);\">...</td></tr>";
					
					Do[
						key = tailKeys[[i]];
						val = data[key];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[key] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[tailKeys]}
					];
					,
					Do[
						key = keys[[i]];
						val = data[key];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[key] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[keys]}
					];
				];
				
				tableHtml = tableHtml <> "</tbody></table>";
				tableHtml = tableHtml <> formatDimensionFooter[ToString[Length[keys]] <> " keys"];
				tableHtml
			],
			
			ListQ[data] && Length[data] > 0 && AllTrue[data, ListQ],
			toHTMLTable[Grid[data]],
			
			ListQ[data],
			Module[{tableHtml, val, isTruncated, headData, tailData},
				isTruncated = Length[data] > $maxRowsToDisplay;
				tableHtml = "<table class=\"wolfram-table\"><thead><tr><th></th><th>Value</th></tr></thead><tbody>";
				
				If[isTruncated,
					headData = Take[data, $headRowsToDisplay];
					tailData = Take[data, -$tailRowsToDisplay];
					
					Do[
						val = headData[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[i] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[headData]}
					];
					
					tableHtml = tableHtml <> "<tr><td colspan=\"2\" style=\"text-align: center; color: var(--jp-ui-font-color3, #888888); font-weight: bold; background-color: var(--jp-layout-color1, #ffffff);\">...</td></tr>";
					
					Do[
						val = tailData[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[Length[data] - Length[tailData] + i] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[tailData]}
					];
					,
					Do[
						val = data[[i]];
						tableHtml = tableHtml <> "<tr><td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5); text-align: right; width: 30px;\">" <> ToString[i] <> "</td><td>" <> formatCell[val] <> "</td></tr>",
						{i, 1, Length[data]}
					];
				];
				
				tableHtml = tableHtml <> "</tbody></table>";
				tableHtml = tableHtml <> formatDimensionFooter[ToString[Length[data]] <> " items"];
				tableHtml
			],
			
			True,
			"<table class=\"wolfram-table\"><tr><td>" <> formatCell[data] <> "</td></tr></table>"
		];
		Return[beautifyHTMLTable[html]];
	];

	toHTMLTable[expr : TableForm[data_, opts___]] := Module[
		{listData, headings, rowH, colH, numRows, numCols, rowHeaders, colHeaders, hasRowH, hasColH, html, row, val,
		 isTruncated, headData, tailData, headRowHeaders, tailRowHeaders, tableCols},
		listData = If[ListQ[data], data, {data}];
		headings = Lookup[Association[opts], TableHeadings, None];
		
		rowH = None;
		colH = None;
		If[MatchQ[headings, {_, _}],
			rowH = headings[[1]];
			colH = headings[[2]];
		];
		
		numRows = Length[listData];
		numCols = If[numRows > 0 && AllTrue[listData, ListQ], Max[Length /@ listData], 1];
		
		rowHeaders = Which[
			ListQ[rowH] && Length[rowH] == numRows, rowH,
			rowH === Automatic, Range[numRows],
			True, {}
		];
		
		colHeaders = Which[
			ListQ[colH] && Length[colH] == numCols, colH,
			colH === Automatic, Range[numCols],
			True, {}
		];
		
		hasRowH = Length[rowHeaders] > 0;
		hasColH = Length[colHeaders] > 0;
		tableCols = numCols + If[hasRowH, 1, 0];
		isTruncated = numRows > $maxRowsToDisplay;
		
		html = "<table class=\"wolfram-table\">";
		
		If[hasColH,
			html = html <> "<thead><tr>";
			If[hasRowH, html = html <> "<th></th>"];
			Do[
				html = html <> "<th>" <> formatCell[c] <> "</th>",
				{c, colHeaders}
			];
			html = html <> "</tr></thead>";
		];
		
		html = html <> "<tbody>";
		
		If[isTruncated,
			headData = Take[listData, $headRowsToDisplay];
			tailData = Take[listData, -$tailRowsToDisplay];
			headRowHeaders = If[hasRowH, Take[rowHeaders, $headRowsToDisplay], {}];
			tailRowHeaders = If[hasRowH, Take[rowHeaders, -$tailRowsToDisplay], {}];
			
			Do[
				row = headData[[i]];
				html = html <> "<tr>";
				If[hasRowH,
					html = html <> "<td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[headRowHeaders[[i]]] <> "</td>"
				];
				If[ListQ[row],
					Do[
						val = If[j <= Length[row], row[[j]], ""];
						html = html <> "<td>" <> formatCell[val] <> "</td>",
						{j, 1, numCols}
					],
					html = html <> "<td>" <> formatCell[row] <> "</td>"
				];
				html = html <> "</tr>",
				{i, 1, Length[headData]}
			];
			
			html = html <> "<tr><td colspan=\"" <> ToString[tableCols] <> "\" style=\"text-align: center; color: var(--jp-ui-font-color3, #888888); font-weight: bold; background-color: var(--jp-layout-color1, #ffffff);\">...</td></tr>";
			
			Do[
				row = tailData[[i]];
				html = html <> "<tr>";
				If[hasRowH,
					html = html <> "<td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[tailRowHeaders[[i]]] <> "</td>"
				];
				If[ListQ[row],
					Do[
						val = If[j <= Length[row], row[[j]], ""];
						html = html <> "<td>" <> formatCell[val] <> "</td>",
						{j, 1, numCols}
					],
					html = html <> "<td>" <> formatCell[row] <> "</td>"
				];
				html = html <> "</tr>",
				{i, 1, Length[tailData]}
			];
			,
			Do[
				row = listData[[i]];
				html = html <> "<tr>";
				If[hasRowH,
					html = html <> "<td style=\"font-weight: bold; background-color: var(--jp-layout-color2, #f5f5f5);\">" <> formatCell[rowHeaders[[i]]] <> "</td>"
				];
				If[ListQ[row],
					Do[
						val = If[j <= Length[row], row[[j]], ""];
						html = html <> "<td>" <> formatCell[val] <> "</td>",
						{j, 1, numCols}
					],
					html = html <> "<td>" <> formatCell[row] <> "</td>"
				];
				html = html <> "</tr>",
				{i, 1, numRows}
			];
		];
		
		html = html <> "</tbody></table>";
		html = html <> formatDimensionFooter[ToString[numRows] <> " rows x " <> ToString[numCols] <> " columns"];
		Return[beautifyHTMLTable[html]];
	];

	toHTMLTable[expr : Grid[data_List, opts___]] := Module[
		{numRows, numCols, isTruncated, headRows, tailRows, spacerRow, truncatedData, formattedData, formattedGrid, htmlFragment},
		numRows = Length[data];
		numCols = If[numRows > 0, Length[First[data]], 0];
		isTruncated = numRows > $maxRowsToDisplay;
		
		If[isTruncated,
			headRows = Take[data, $headRowsToDisplay];
			tailRows = Take[data, -$tailRowsToDisplay];
			spacerRow = If[numCols > 0, Join[{"..."}, Table[SpanFromLeft, numCols - 1]], {"..."}];
			truncatedData = Join[headRows, {spacerRow}, tailRows];
			,
			truncatedData = data;
		];
		
		formattedData = Map[formatGridCell, truncatedData, {2}];
		formattedGrid = Grid[formattedData, opts];
		htmlFragment = Quiet[ExportString[formattedGrid, "HTMLFragment"]];
		If[FailureQ[htmlFragment] || !StringQ[htmlFragment],
			Return[$Failed];
		];
		
		htmlFragment = htmlFragment <> formatDimensionFooter[ToString[numRows] <> " rows x " <> ToString[numCols] <> " columns"];
		Return[beautifyHTMLTable[htmlFragment]];
	];

	toHTMLTable[expr_] := $Failed;

	(* generate HTML representation for any expression (including text and graphics) *)
	toHTML[expr_] :=
		If[isTableQ[expr],
			Module[{htmlTable = toHTMLTable[expr]},
				If[StringQ[htmlTable], htmlTable, toHTML[Shallow[expr]]]
			],
			If[
				textQ[expr] || isMathExprQ[expr] || Head[expr] === TeXForm || $outputSetToTeXForm,
				If[((Head[expr] === TeXForm) || ($outputSetToTeXForm) || isMathExprQ[expr]),
					Module[
						{latexText},
						latexText = toText[If[Head[expr] === TeXForm, expr, TeXForm[expr]], Infinity];
						latexText = sanitizeLaTeX[latexText];
						StringJoin["<div style=\"text-align: left;\"><style>mjx-container[display=\"true\"] { align-items: flex-start !important; text-align: left !important; } .MathJax_Display { text-align: left !important; }</style>$$", latexText, "$$</div>"]
					],
					toOutTextHTML[expr]
				],
				Module[
					{svgStr},
					svgStr = toSVGString[$trueFormatType[expr]];
					If[
						StringQ[svgStr],
						svgStr,
						toOutImageHTML[expr]
					]
				]
			]
		];

	(* build a complete Jupyter MIME bundle for a single expression result *)
	(* Returns an Association with "data" and "metadata" keys following the Jupyter protocol *)
	(* See https://jupyter-client.readthedocs.io/en/stable/messaging.html#display-data *)
	toMimeBundle[expr_] :=
		Module[
			{
				(* the processed expression applying format type *)
				processedExpr,

				(* text/plain fallback - always generated *)
				plainText,

				(* SVG export result *)
				svgStr,

				(* PNG byte array and base64 *)
				pngData, pngBase64,

				(* PNG image dimensions for metadata *)
				pngWidth, pngHeight,

				(* accumulated MIME data and metadata dicts *)
				mimeData, mimeMeta
			},

			(* --- Table/Grid Path: Intercept early to generate beautiful HTML tables --- *)
			If[isTableQ[expr],
				Module[
					{
						htmlTable,
						dataAssoc
					},
					plainText = toText[expr];
					htmlTable = toHTMLTable[expr];
					If[StringQ[htmlTable],
						dataAssoc = Association[
							"text/plain" -> plainText,
							"text/html" -> htmlTable
						];
						Return[
							Association[
								"data" -> dataAssoc,
								"metadata" -> Association[]
							]
						];
					];
				];
			];

			(* --- Manipulate Path: Intercept early to generate structured widget data --- *)
			If[Head[expr] === Manipulate,
				Return[
					Association[
						"data" -> Association[
							"application/x-wolfram-manipulate" -> serializeManipulate[expr]
						],
						"metadata" -> Association[]
					]
				];
			];

			processedExpr = $trueFormatType[expr];

			(* always generate a text/plain representation as required by the Jupyter spec *)
			plainText = toText[expr];

			(* --- Graphics path (CHECKED FIRST, before textQ) ---
			   graphicsQ uses head-based detection, independent of $canUseFrontEnd.
			   Rasterize and ExportString[...,"SVG"] work in headless Wolfram Engine. *)
			If[graphicsQ[expr],
				(* skip to graphics path directly *)
				Goto[graphicsPath];
			];

			(* --- Text path: pure text/symbol expressions or LaTeX/Math expressions --- *)
			If[textQ[expr] || isMathExprQ[expr] || (Head[expr] === TeXForm) || $outputSetToTeXForm,
				Module[
					{
						isTeX,
						latexText,
						dataAssoc
					},
					isTeX = ((Head[expr] === TeXForm) || ($outputSetToTeXForm) || isMathExprQ[expr]);
					dataAssoc = Association[
						"text/plain" -> plainText
					];
					
					If[isTeX,
						(* Generate the LaTeX representation *)
						latexText = toText[If[Head[expr] === TeXForm, expr, TeXForm[expr]], Infinity];
						latexText = sanitizeLaTeX[latexText];
						AssociateTo[dataAssoc, "text/latex" -> latexText];
						(* For HTML, wrap it in double dollars to trigger client-side MathJax, aligned left with style overrides *)
						AssociateTo[dataAssoc, "text/html" -> StringJoin["<div style=\"text-align: left;\"><style>mjx-container[display=\"true\"] { align-items: flex-start !important; text-align: left !important; } .MathJax_Display { text-align: left !important; }</style>$$", latexText, "$$</div>"]];
					,
						(* Standard text/html output *)
						AssociateTo[dataAssoc, "text/html" -> toOutTextHTML[expr]];
					];

					Return[
						Association[
							"data" -> dataAssoc,
							"metadata" -> Association[]
						]
					];
				];
			];

			(* --- Graphics/Image path: SVG preferred, PNG as fallback --- *)
			Label[graphicsPath];
			mimeData = Association["text/plain" -> plainText];
			mimeMeta = Association[];

			(* Attempt SVG export (lossless vector; works for most 2D Wolfram graphics) *)
			svgStr = toSVGString[processedExpr];
			If[StringQ[svgStr],
				AssociateTo[mimeData, "image/svg+xml" -> svgStr];
				(* SVG metadata: empty dict; frontend uses viewBox for sizing *)
				AssociateTo[mimeMeta, "image/svg+xml" -> Association[]];
			];

			(* Always generate a PNG as universal fallback *)
			(* Try direct rasterization first *)
			pngData = toImageData[processedExpr];
			If[FailureQ[pngData],
				(* Fallback 1: rasterize a Shallow form *)
				pngData = toImageData[$trueFormatType[Shallow[expr]]];
			];
			If[FailureQ[pngData],
				(* Fallback 2: rasterize $Failed symbol *)
				pngData = toImageData[$trueFormatType[$Failed]];
			];

			If[!FailureQ[pngData],
				pngBase64 = BaseEncode[pngData];
				(* Extract image dimensions for metadata (divide by 2: 144dpi -> 72 logical px) *)
				Block[
					{parsedImg},
					parsedImg = Quiet[ImportByteArray[pngData, "PNG"]];
					If[Head[parsedImg] === Image,
						{pngWidth, pngHeight} = ImageDimensions[parsedImg];
						,
						{pngWidth, pngHeight} = {0, 0};
					];
				];
				AssociateTo[mimeData, "image/png" -> pngBase64];
				(* Provide width/height in metadata at logical resolution *)
				If[pngWidth > 0 && pngHeight > 0,
					AssociateTo[mimeMeta, "image/png" ->
						Association[
							"width"  -> Ceiling[pngWidth / 2],
							"height" -> Ceiling[pngHeight / 2]
						]
					];
				];
			,
				(* All rasterization attempts failed: use hard-coded $Failed image *)
				AssociateTo[mimeData, "image/png"  -> failedInBase64];
			];

			Return[Association["data" -> mimeData, "metadata" -> mimeMeta]];
		];

	(* helper for TCP-based stdin requests *)
	getStdinFromSocket[prompt_String, type_String] := Module[
		{socket, req, response},
		If[!IntegerQ[WolframLanguageForJupyter`Private`$stdinPort] || WolframLanguageForJupyter`Private`$stdinPort <= 0,
			Return[If[type === "Input", $Failed, ""]];
		];
		
		(* Connect to the Python stdin server *)
		socket = Quiet[SocketConnect[{"127.0.0.1", WolframLanguageForJupyter`Private`$stdinPort}]];
		If[FailureQ[socket],
			Return[If[type === "Input", $Failed, ""]];
		];
		
		(* Send request *)
		req = ExportString[Association["prompt" -> prompt, "type" -> type], "JSON", "Compact" -> True];
		WriteString[socket, req];
		
		(* Block waiting for reply data *)
		SocketWaitNext[{socket}];
		
		(* Read reply *)
		response = ReadString[socket];
		Close[socket];
		
		If[FailureQ[response] || !StringQ[response],
			Return[If[type === "Input", $Failed, ""]];
		];
		
		If[type === "Input",
			Quiet[ToExpression[response, InputForm, Identity]],
			response
		]
	];
	getStdinFromSocket[prompt_, type_String] := getStdinFromSocket[ToString[prompt], type];

	(* Redefine Input and InputString to route via socket *)
	Unprotect[Input, InputString];
	ClearAttributes[{Input, InputString}, ReadProtected];
	DownValues[Input] = {};
	DownValues[InputString] = {};
	Input[prompt_ : ""] := getStdinFromSocket[prompt, "Input"];
	InputString[prompt_ : ""] := getStdinFromSocket[prompt, "InputString"];
	parseVariableSpec[spec_] := Module[
		{varName, initVal, minVal, maxVal, stepVal, choices, type, nameStr},
		If[ListQ[spec] && Length[spec] >= 2,
			If[ListQ[spec[[1]]],
				varName = spec[[1, 1]];
				initVal = spec[[1, 2]];
			,
				varName = spec[[1]];
				initVal = None;
			];
			nameStr = ToString[varName];
			
			If[ListQ[spec[[2]]],
				choices = spec[[2]];
				If[initVal === None, initVal = First[choices]];
				If[Sort[choices] === {False, True},
					type = "Checkbox";
				,
					type = "Dropdown";
				];
				Return[Association[
					"name" -> nameStr,
					"type" -> type,
					"initial" -> initVal,
					"choices" -> choices
				]];
			];
			
			minVal = spec[[2]];
			maxVal = spec[[3]];
			If[Length[spec] >= 4,
				stepVal = spec[[4]];
			,
				stepVal = None;
			];
			If[initVal === None, initVal = minVal];
			
			Return[Association[
				"name" -> nameStr,
				"type" -> "Slider",
				"initial" -> initVal,
				"min" -> minVal,
				"max" -> maxVal,
				"step" -> stepVal
			]];
		];
		$Failed
	];

	serializeManipulate[HoldPattern[Manipulate[expr_, vars__]]] := Module[
		{varList, parsedVars},
		varList = {vars};
		parsedVars = Map[parseVariableSpec, varList];
		Association[
			"type" -> "Manipulate",
			"expression" -> ToString[Hold[expr], InputForm],
			"variables" -> DeleteCases[parsedVars, $Failed]
		]
	];

	evaluateManipulate[exprStr_String, bindings_Association] := Module[
		{heldExpr, rules, substituted, evalResult, mimeBundle},
		
		(* Redirect buffers *)
		loopState["capturedStdout"] = {};
		loopState["capturedStderr"] = {};
		loopState["LastMessages"] = {};
		loopState["printFunction"] = (AppendTo[loopState["capturedStdout"], #1] &);
		
		messageFormatter[messageName_, messageText_] :=
			Module[{msgString},
				msgString = ToString[System`ColonForm[HoldForm[messageName], messageText]];
				AppendTo[loopState["LastMessages"], msgString];
				AppendTo[loopState["capturedStderr"], msgString];
				msgString
			];
		SetAttributes[messageFormatter, HoldAll];
		Internal`$MessageFormatter = messageFormatter;
		
		heldExpr = ToExpression[exprStr, InputForm];
		rules = Symbol[#1] -> bindings[#1] & /@ Keys[bindings];
		substituted = ReplaceAll[heldExpr, rules];
		
		evalResult = Quiet[ReleaseHold[substituted]];
		
		loopState["printFunction"] = False;
		Unset[messageFormatter];
		Unset[Internal`$MessageFormatter];
		
		mimeBundle = toMimeBundle[evalResult];
		
		Association[
			"status" -> "ok",
			"mime_bundle" -> mimeBundle,
			"captured_stdout" -> StringJoin[loopState["capturedStdout"]],
			"captured_stderr" -> loopState["capturedStderr"]
		]
	];

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotOutputHandlingUtilities *)
