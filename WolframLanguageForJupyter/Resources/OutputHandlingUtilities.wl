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

	(* generate HTML representation for any expression (including text and graphics) *)
	toHTML[expr_] :=
		If[
			textQ[expr],
			toOutTextHTML[expr],
			Module[
				{svgStr},
				svgStr = toSVGString[$trueFormatType[expr]];
				If[
					StringQ[svgStr],
					svgStr,
					toOutImageHTML[expr]
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

			(* --- Text path: pure text/symbol expressions --- *)
			If[textQ[expr],
				Return[
					Association[
						"data" -> Association[
							"text/plain" -> plainText,
							"text/html"  -> toOutTextHTML[expr]
						],
						"metadata" -> Association[]
					]
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

	(* end the private context for WolframLanguageForJupyter *)
	End[]; (* `Private` *)

(************************************
	Get[] guard
*************************************)

] (* WolframLanguageForJupyter`Private`$GotOutputHandlingUtilities *)
