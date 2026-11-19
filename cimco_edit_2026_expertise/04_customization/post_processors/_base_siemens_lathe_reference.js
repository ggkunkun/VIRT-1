// Use these variables to setup the post processor for the 
// correct output 
globals = {
	decimalMark: ".",
	linebreak: "\n",
	variableDelimeter: " ",
	tolerance: 0.02,
	showSequenceNumbers: true,
	sequenceNumberStart: 10,
	sequenceNumberIncrement: 5,
	xDiameterProg: true,
	iDiameterProg: true,
	useRadius: true,
	absoluteArcCenter: false,
	xAxisName: "X",
	zAxisName: "Z",
	iAxisName: "I",
	kAxisName: "K",
	xAxisFactor: 1.0, // xAxisfactor is only set to 1 or -1 in order to reverse the axis USE xDiameterProg TO CORRECT FOR DIAMETER PROGRAMMING
	zAxisFactor: 1.0  // zAxisfactor is only set to 1 or -1 in order to reverse the axis
};

PostInfo = {
	title: 'Siemens Turning',
	summary: 'Generic Siemens turning Post Processor.',
	description: 'This post Processor is used for Siemens a lathe with the coordinates X up Z right.',
	author: 'CIMCO A/S',
	version: "1.0",
	type: POST_TYPE_TURN
};

propertyNames = {
	RetractPlane: 1,
	SafeDistance: 1,
	ReferenceHeight: 1,
	Depth: 1,
	PlungeFeedRate: 1,
	RetractFeedRate: 1,
	FirstPeckDepth: 1,
	SubsequentPeckDepth: 1
};

TurnDrillingFields = [
{
	name: "Drilling",
	isLonghand: true,
	plungingFeedrate: true,
	retractFeedrate: true,
	usePecking: false,
	firstPeckDepth: false,
	subsequentPeckDepths: false,
	peckClearance: false,
	peckRetract: false,
	pitch: false,
	uselowerDwell: true,
	useUpperDwell: false,
},
{
	name: "Peck Drilling",
	isLonghand: true,
	plungingFeedrate: true,
	retractFeedrate: true,
	usePecking: true,
	firstPeckDepth: true,
	subsequentPeckDepths: true,
	peckClearance: true,
	peckRetract: true,
	pitch: false,
	uselowerDwell: true,
	useUpperDwell: true,
},
{
	name: "Drilling G83",
	isLonghand: false,
	plungingFeedrate: true,
	retractFeedrate: false,
	usePecking: false,
	firstPeckDepth: false,
	subsequentPeckDepths: false,
	peckClearance: false,
	peckRetract: false,
	pitch: false,
	uselowerDwell: true,
	useUpperDwell: false,
},
{
	name: "Tapping CW G84",
	isLonghand: false,
	plungingFeedrate: false,
	retractFeedrate: false,
	usePecking: false,
	firstPeckDepth: false,
	subsequentPeckDepths: false,
	peckClearance: false,
	peckRetract: false,
	pitch: true,
	uselowerDwell: false,
	useUpperDwell: false,
}
];

TurnThreadingFields = [
{
	name: "Canned G76",
	pullOffDistance: true,
	inFeed: true,
	taper: true,
},
{
	name: "Box G92",
	pullOffDistance: false,
	inFeed: false,
	taper: true,
}
];

var commentFront = "(";
var commentBack = ")";

var gFormat;
var fFormat;
var fFormatOneDecimal;


var xFormat;
var zFormat;

var iFormat;
var kFormat;

var pFormat;

var radiusFormat;

var gOutput;

var feedOutput;
var feedOutputOneDecimal;
var compensationOutput;

var xOutput;
var zOutput;

var iOutput;
var kOutput;

var pOutput;
var qOutput;
var rOutput;
var radiusOutput;

var feedRates;
var lastCompensation;

var dwellOutput;

var sequenceNumber;

var distR;
var distEndDepthR;
var drillHeaderCalled = false;
var drillIsFirst;
var drillHeader;

function writeBlock() {
	if (globals.showSequenceNumbers) {
		writeWords2("N" + sequenceNumber, arguments);
		sequenceNumber += globals.sequenceNumberIncrement;
	} else {
		writeWords(arguments);
	}
}

function getFeedRate(movement) {
	if (! (movement in feedRates)) {
		return "";
	}
	return feedOutput.format(feedRates[movement]);
}

function getCompensation() {
	var gCode;
	switch (lastCompensation) {
		case COMPENSATION_LEFT : 
			if (globals.xAxisFactor * globals.zAxisFactor > 0)
			{
				// Right hand coordinates system
				gCode = 41;
			}
			else 
			{
				// Left hand coordinate system
				gCode = 42;
			}
		break;
		case COMPENSATION_RIGHT: 
			if (globals.xAxisFactor * globals.zAxisFactor > 0) 
			{
				// Right hand coordinates system
				gCode = 42;
			}
			else
			{
				// Left hand coordinate system
				gCode = 41;
			}
		break;
		case COMPENSATION_OFF  : 
			gCode = 40; 
		break;
	}
	if (lastCompensation != null) {
		return compensationOutput.format(gCode);
	}
	return "";
}

function onInit() {
	// createFormat handles value pairs to control the behaviour of the format
	// Their order is without importance and the value pairs supported and their default values are:
	//	Name			Default value	Description
	// 	prefix..........""..............What should be written in front of the value
	// 	width			0				Indicates the width or the integer part of the value
	// 	zeropad.........false...........Zeropad relates to the integer part of the value and if a width of
	//									4 is set and zeropad is set to true 1 would be written as 0001
	// 	decimals........0...............Indicates the number of decimals the value should be formatted with
	// 	scale			1				This is a scale factor that the value is multiplied by 		
	// 	forceDecimal....false...........Forces the decimal part of the value to always be written wit the number
	//									of decimals indicated in decimals so if decimals is set to 3 and forceDecimals
	//									is set to true 3.0 would be written as 3.000
	// 	forceSign.......false...........Makes it possible to always force a sign. So 4.25 would be written as +4.25

	// Examples:
	// myFormat = createFormat({prefix: "H", decimals: 1, width:3, zeropad: true}) 2.7 becomes H002,7
	// myFormat = createFormat({decimals: 3, forceDecimals: true, forceSign: true}) 4.5 becomes +4.500

	
	gFormat = createFormat({prefix: "G", decimals: 0, width: 2, forceDelim:false});
	fFormat = createFormat({decimals: 0, prefix: "F"});
	fFormatTwoDecimals = createFormat({prefix: "F", decimals: 2, forceDecimal: true}); 
	fFormatOneDecimal = createFormat({prefix: "F", decimals: 1, forceDecimal: true});
	fFormatThreeDecimals = createFormat({prefix: "F", decimals: 3, forceDecimals: true});
	twoDigitIntegerFormat = createFormat({decimals: 0, width:2});
	integerFormat = createFormat({decimals: 0});

	if (globals.xDiameterProg) 
	{
		xFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.xAxisFactor * 2.0});
	}
	else
	{
		xFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.xAxisFactor});
	}
	
	zFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.zAxisFactor});

	if (globals.iDiameterProg) 
	{
		iFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.xAxisFactor * 2.0});
	}
	else
	{
		iFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.xAxisFactor});
	}
	
	kFormat = createFormat({decimals: 3, forceDecimal: true, scale: globals.zAxisFactor});

	intFormat = createFormat({decimals: 0});
	mFormat = createFormat({decimals: 0, width: 2});

	pFormat = createFormat({decimals: 0}); 

	radiusFormat = createFormat({decimals: 3, forceDecimal: true});

	gOutput = createVariable({}, gFormat);

	feedOutput = createVariable({}, fFormat);
	feedOutputOneDecimal = createVariable({}, fFormatOneDecimal);
	feedOutputTwoDecimals = createVariable({}, fFormatTwoDecimals);
	fOutputThreeDecimals = createVariable({force: true}, fFormatThreeDecimals);
	
	compensationOutput = createVariable({}, gFormat);

	xOutput = createVariable({prefix: globals.xAxisName}, xFormat);
	zOutput = createVariable({prefix: globals.zAxisName}, zFormat);

	iOutput = createVariable({prefix: globals.iAxisName, force: true}, iFormat);
	kOutput = createVariable({prefix: globals.kAxisName, force: true}, kFormat);
	
	mOutput = createVariable({prefix: "M", force: true}, mFormat);

	pOutput = createVariable({prefix: "P", force: true}, pFormat);
	qOutput = createVariable({prefix: "Q", force: true}, zFormat);
	rOutput = createVariable({prefix: "R", force: true}, zFormat);

	radiusOutput = createVariable({prefix: "CR=", force: true},radiusFormat);

	sOutput = createVariable({prefix: "S", force: true}, intFormat);
	tOutput = createVariable({prefix: "T", force: true}, mFormat);
	
	genericRealOutput = createVariable({},xFormat);

	feedRates = {};
	lastCompensation = null;
	
	twoDigitIntegerOutput = createVariable({force:true}, twoDigitIntegerFormat);
	qIntegerOutput = createVariable({prefix: "Q", force: true},integerFormat);
	rIntegerOutput = createVariable({prefix: "R", force: true},integerFormat);

	dwellOutput = createVariable({prefix: "X", force: true}, zFormat);
	
	sequenceNumber = globals.sequenceNumberStart;

	drillIsFirst = false;
	drillHeader = null;
}

function threadEqualDepthFirstDepth(header)
{
  var finalDepth = (header.majorDiameter - header.minorDiameter) / 2.0 - header.stockToLeave;
  
  var numberOfCuts =  Math.ceil(finalDepth / header.fistCutDepth);

  var cutDepth = finalDepth/header.numberOfCuts;
  
  var depthList = [];
  
  var currentCutDepth = 0;

  for (var i=0;i<header.numberOfCuts;i++ )
  {
    currentCutDepth += cutDepth;
    depthList.push(currentCutDepth);
  }
		
  return depthList;
}

function threadEqualDepthNumberOfSteps(header)
{
  var finalDepth = (header.majorDiameter - header.minorDiameter) / 2.0 - header.stockToLeave;
  
  var cutDepth = finalDepth/header.numberOfCuts;
  
  var depthList = [];
  
  var currentCutDepth = 0;
  for (var i=0; i<header.numberOfCuts; i++ )
  {
    currentCutDepth += cutDepth;
    depthList.push(currentCutDepth);
  }
 
  return depthList;
}

function threadEqualAreaFirstDepth(header)
{
  var depthList = [];
  
  // Assumes angles are in radians. Area of triangle is factor * depth * depth
  var factor = (Math.tan(header.threadAngle) + Math.tan(header.includedThreadAngle - header.threadAngle)) / 2.0;
  var finalDepth = (header.majorDiameter - header.minorDiameter) / 2.0 - header.stockToLeave;
  var areaStep = factor * header.firstCutDepth * header.firstCutDepth;
  
  var currentArea = 0;
  var done = false;
  var i = 0;
  while (!done) 
  {
    currentArea += areaStep;
    var currentDepth = Math.sqrt(currentArea / factor);
    if (currentDepth > finalDepth)
    {
      currentDepth =  finalDepth;
      done = true;
    }
    depthList.push(currentDepth);
	i++;
  }
		
  return depthList;
}

function threadEqualAreaNumberOfSteps(header)
{
  // Assumes angles are in radians. Area of triangle is factor * depth * depth
  var factorThreadAngle = Math.tan(header.threadAngle);
  var factorThreadIncludedAngle = Math.tan(header.includedThreadAngle - header.threadAngle);
  var factor = (Math.tan(header.threadAngle) + Math.tan(header.includedThreadAngle - header.threadAngle)) / 2.0;
  var finalDepth = (header.majorDiameter - header.minorDiameter) / 2.0 - header.stockToLeave;
  var finalArea = factor * finalDepth * finalDepth;
  var areaStep = finalArea / header.numberOfCuts;
  
  var depthList = [];

  for (var i = 0; i < header.numberOfCuts; ++i) 
  {
    currentArea = (i + 1) * areaStep;
    currentDepth = Math.sqrt(currentArea / factor);
    depthList.push(currentDepth);
  }

  return depthList;
}

function BuildThreadDepthList(header)
{
  switch(header.cuttingType) 
  {
  case 0: // The cuts have equal depth
    {
      switch(header.cuttingDepthUsed) 
      {
      case 0: // Calculations are based on the first cutting depth
        return threadEqualDepthFirstDepth(header);
        break;
      case 1: // Calculations are based on the number of cuts taken
        return threadEqualDepthNumberOfSteps(header);
        break;
      }
    }
    break;
  case 1: // The cuts have equal pressure
    {
      switch(header.cuttingDepthUsed) 
      {
      case 0: // Calculations are based on the first cutting depth
        return threadEqualAreaFirstDepth(header);
        break;
      case 1:// Calculations are based on the number of cuts taken
        return threadEqualAreaNumberOfSteps(header);
        break;
      }
    }
    break;
  }
}

function onThreading(header)
{
	var testString;
	// First generate a list with all cutting depths
	var depthList = BuildThreadDepthList(header);

	var taperTypeFront = 0;
	var taperTypeBack = 1;

	var taperAngle = header.taperAngle;

	// Calculate all the values later used in the various thread operations

	var zStart = Math.min(header.zStart,header.zEnd);
    var zEnd = Math.max(header.zStart,header.zEnd);
	var zFinalStart = zStart - header.accelerationDistance;
    var zFinalEnd = zEnd + header.overcutDistance;
    if (header.isRightToLeft)
    {
		zStart = Math.max(header.zStart,header.zEnd);
		zEnd = Math.min(header.zStart,header.zEnd);
		zFinalStart = zStart + header.accelerationDistance;
		zFinalEnd = zEnd  - header.overcutDistance;
    }

	onComment(header.name);

	// Calculate all the values based on: 
	// internal/external 
	// Taper front/taper back
	// left to right / right to left

	var xFinalEnd;
	var xFinalStart;
	var xRetract;


	var totalDepth = (header.majorDiameter - header.minorDiameter)/2.0;

	if (header.isExternalThread && !header.isRightToLeft &&
	header.taperType == taperTypeFront)
	{
		var deltaFinalStart = (zEnd - zFinalStart) * Math.tan(taperAngle);
		xFinalStart = (2.0 * deltaFinalStart + header.minorDiameter)/2.0;
		var deltaFinalEnd = (zFinalEnd - zEnd) * Math.tan(-taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.minorDiameter)/2.0;
		xRetract = Math.max(xFinalStart,xFinalEnd) + totalDepth + header.stockClearance;
	}
	else if (header.isExternalThread && !header.isRightToLeft &&
	header.taperType == taperTypeBack)
	{
		var deltaFinalStart = (zStart - zFinalStart) * Math.tan(-taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.minorDiameter)/2.0;
		var deltaFinalEnd = (zFinalEnd - zStart) * Math.tan(taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.minorDiameter)/2.0;
		xRetract = Math.max(xFinalStart,xFinalEnd) + totalDepth + header.stockClearance;
	}
	else if (header.isExternalThread && header.isRightToLeft &&
	header.taperType == taperTypeFront)
	{
		var deltaFinalStart = (zFinalStart - zStart) * Math.tan(-taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.minorDiameter)/2.0;
		var deltaFinalEnd = (zStart - zFinalEnd) * Math.tan(taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.minorDiameter)/2.0;
		xRetract = Math.max(xFinalStart,xFinalEnd) + totalDepth + header.stockClearance;
	}
	else if (header.isExternalThread && header.isRightToLeft &&
	header.taperType == taperTypeBack)
	{
		var deltaFinalStart = (zFinalStart - zEnd) * Math.tan(taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.minorDiameter)/2.0;
		var deltaFinalEnd = (zEnd - zFinalEnd) * Math.tan(-taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.minorDiameter)/2.0;
		xRetract = Math.max(xFinalStart,xFinalEnd) + totalDepth + header.stockClearance;
	}
	else if (!header.isExternalThread && !header.isRightToLeft &&
	header.taperType == taperTypeFront)
	{
		var deltaFinalStart = (zEnd - zFinalStart) * Math.tan(taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.majorDiameter)/2.0;
		var deltaFinalEnd = (zFinalEnd - zEnd) * Math.tan(-taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.majorDiameter)/2.0;
		xRetract = Math.min(xFinalStart,xFinalEnd) - totalDepth - header.stockClearance;
	}
	else if (!header.isExternalThread && !header.isRightToLeft &&
	header.taperType == taperTypeBack)
	{
		var deltaFinalStart = (zStart - zFinalStart) * Math.tan(-taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.majorDiameter)/2.0;
		var deltaFinalEnd = (zFinalEnd - zStart) * Math.tan(taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.majorDiameter)/2.0;
		xRetract = Math.min(xFinalStart,xFinalEnd) - totalDepth - header.stockClearance;
	}
	else if (!header.isExternalThread && header.isRightToLeft &&
	header.taperType == taperTypeFront)
	{
		var deltaFinalStart = (zFinalStart - zStart) * Math.tan(-taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.majorDiameter)/2.0;
		var deltaFinalEnd = (zStart - zFinalEnd) * Math.tan(taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.majorDiameter)/2.0;
		xRetract = Math.min(xFinalStart,xFinalEnd) - totalDepth - header.stockClearance;
	}
	else if (!header.isExternalThread && header.isRightToLeft &&
	header.taperType == taperTypeBack)
	{
		var deltaFinalStart = (zFinalStart - zEnd) * Math.tan(taperAngle);
		xFinalStart = (2.0*deltaFinalStart+header.majorDiameter)/2.0;
		var deltaFinalEnd = (zEnd - zFinalEnd) * Math.tan(-taperAngle);
		xFinalEnd = (2.0*deltaFinalEnd + header.majorDiameter)/2.0;
		xRetract = Math.min(xFinalStart,xFinalEnd) - totalDepth - header.stockClearance;
	}
    
	var taper = xFinalStart-xFinalEnd;

	if (header.name == "Canned G76") 
	{
		// Correct the starting position for the infeed angle
		var deltaInfeed = Math.tan(header.infeedAngle) * totalDepth;

		var zEntry = zFinalStart + deltaInfeed;

        if (zFinalStart < zFinalEnd)
        {
			zEntry = zFinalStart - deltaInfeed;  
        }

		// Calculate the offset for the threads with more than one start
		var zDelta = -header.threadLead / header.numberOfStarts;

		if (zStart > zEnd) 
		{
			zDelta =  header.threadLead / header.numberOfStarts;
		}

		for(var startCount = 0; startCount < header.numberOfStarts; startCount++)
		{
			

			var g = gOutput.format(0);

			var x = xOutput.format(xRetract);
			var z = zOutput.format(zEntry + startCount * zDelta);

			writeBlock(g, x, z);

			g = gOutput.format(76);

			var p = "P";		
			p += twoDigitIntegerOutput.format(header.numberOfSpringPasses);
			var pulloffFactor = Math.floor(header.pullOffDistance / header.threadLead * 10);
			p += twoDigitIntegerOutput.format(pulloffFactor);
			p += twoDigitIntegerOutput.format(Math.floor(180.0/ Math.PI * header.infeedAngle + 0.5));

			var q = qOutput.format(0.0);
			var r = rOutput.format(header.stockToLeave);

			writeBlock(g, p, q, r);
			
			var x = xOutput.format(xFinalEnd);
			var z = zOutput.format(zFinalEnd);


			p = pOutput.format(totalDepth * 10000);

			q = qIntegerOutput.format(header.firstCutDepth * 10000);

			r = rOutput.format(-taper);
		
			var f = fOutputThreeDecimals.format(header.threadLead);

			writeBlock(g, x, z, p, q, r, f);
		}
	}
	else if (header.name == "Box G92") 
	{
		

		// Recalculate the real depth list based on the taper
		var origDepth;
		var realDepthList = [];

		// Calculate the absolute depths based on the actual depth and diameter
		for (var i=0; i < depthList.length; i++) 
		{
			var currentDepth = xFinalEnd + (totalDepth - depthList[i]);
			if (!header.isExternalThread)
			{
				currentDepth = xFinalEnd - (totalDepth - depthList[i]);
			}
			realDepthList.push(currentDepth);
		}

		for (var startCount = 0; startCount < header.numberOfStarts; startCount++)
		{
			var deltaZ = -startCount*(header.threadLead/header.numberOfStarts);

			if (zStart > zEnd) 
			{
				deltaZ =  startCount*(header.threadLead/header.numberOfStarts);
			}

			var currentDepth = 0;
			for (var depthCounter=0; depthCounter < realDepthList.length; depthCounter++) 
			{
				currentDepth = realDepthList[depthCounter];
				if (depthCounter == 0) 
				{
					
					var g = gOutput.format(0);
					var x = xOutput.format(xRetract)	;
					var z = zOutput.format(zFinalStart );
					
					writeBlock(g, x, z);

					g = gOutput.format(92);
					x = xOutput.format(currentDepth);
					z = zOutput.format(zFinalEnd);
					var r = "";
					if (taper != 0.0) 
					{
						r = rOutput.format(taper);
					}
					var f = fOutputThreeDecimals.format(header.threadLead);

					writeBlock(g, x, z, r, f);
				}
				else
				{
					var x = xOutput.format(currentDepth);
					writeBlock(x);
				}
			}
			
			for(var springPassCounter=0; springPassCounter<header.numberOfSpringPasses;springPassCounter++)
			{
				xOutput.reset();
				var x = xOutput.format(currentDepth);
				writeBlock(x);
			}
			
		}

		var g = gOutput.format(0);
		var x = xOutput.format(xRetract);
		
		writeBlock(g, x);
	}
}

// Not used in the lathe post
function onDrillingHeader(header)
{

}
// Not used in the lathe post
function onDrillingPoint(){

}
// Not used in the lathe post
function onDrillingFooter(){

}

function onAxisSubstitutionStart(axisName, diameter, axisTollerance){

}

function onAxisSubstitutionEnd() {

}

function onSpindleRotation(rotation){

}

function onToolChange(toolData)
{
	var m = mOutput.format(6);
	var t = tOutput.format(toolData.toolNumber);
	var s = sOutput.format(toolData.spindleSpeed);
	var f = feedOutput.format(toolData.feedrate);
	writeBlock(t, m, s, f);
}

function onDrilling(drillHeader)
{
	var retractDistance = drillHeader.retractDistance;
	var safeDistance = drillHeader.safeDistance;
	var startDepth = drillHeader.startDepth;
	var endDepth = drillHeader.endDepth;
	var movePlungingFeedrate = MOVE_LAST + 1;
	var moveRetractFeedrate = MOVE_LAST + 2;

	// Set custom feedrates for plunging and retract if these are used
	if (drillHeader.usePlungingFeedrate) 
	{
		setFeedrate(movePlungingFeedrate,drillHeader.plungingFeedrate);
		// Retract feedrate is only ever used if the plunging feedrate is used
		if (drillHeader.useRetractFeedrate) 
		{
			setFeedrate(moveRetractFeedrate,drillHeader.retractFeedrate);
		}else
		{
			moveRetractFeedrate = MOVE_RAPID;
		}
	}else
	{
		movePlungingFeedrate = MOVE_CUTTING;
		moveRetractFeedrate = MOVE_RAPID;
	}

	onComment(drillHeader.name);

	if (drillHeader.isLonghand) 
	{
	// Add all the longhand drilling operations here
		if (drillHeader.name == "Drilling")
		{
			// Move rapidly down to the safe distance
			onLinearZ(safeDistance,MOVE_RAPID);
			// Now drill to the end depth
			onLinearZ(endDepth,movePlungingFeedrate);

			// Dwell at the bottom
			if (drillHeader.useLowerDwell) 
			{
				onDwell(drillHeader.lowerDwell/1000);
			};

			// Move back in one move if no retractFeedrate is defined or two moves if it is
			if (moveRetractFeedrate != MOVE_RAPID) 
			{
				onLinearZ(safeDistance,moveRetractFeedrate);
				onLinearZ(retractDistance,MOVE_RAPID);
			}else
			{
				onLinearZ(retractDistance,moveRetractFeedrate);
			}
		}
		else if (drillHeader.name == "Peck Drilling")
		{
			// Move rapidly down to the safe distance
			onLinearZ(safeDistance,MOVE_RAPID);

			// Calculate the moves to the end depth using pecking
			// An array will hold the depths for each peck
			var isFirstPeck = true;
			var depthArray = {};
			var depthCount = 0;
			var peckDepth = drillHeader.firstPeckDepth;
			var restDepth = startDepth - endDepth;

			for (depthCount = 0;restDepth > peckDepth ; depthCount++) 
			{
				restDepth = restDepth - peckDepth;
				depthArray[depthCount] = restDepth + endDepth;
				if(isFirstPeck == true)
				{
					isFirstPeck = false;

					if (drillHeader.subsequentPecksDepths != 0.0) 
					{
						peckDepth = drillHeader.subsequentPecksDepths;
					}
				}
			}

			if(restDepth != 0.0)
			{
				depthArray[depthCount] = endDepth;
			}
			

			for ( var i = 0; i <= depthCount;++i) 
			{
				onLinearZ(depthArray[i],movePlungingFeedrate);

     			if (drillHeader.useLowerDwell) 
				{
					onDwell(drillHeader.lowerDwell/1000);
				};

				if (drillHeader.packRetract != 0.0) 
				{
					onLinearZ(depthArray[i] + drillHeader.packRetract,moveRetractFeedrate);
				};

				if (drillHeader.useUpperDwell) 
				{
					onDwell(drillHeader.upperDwell/1000);
				};
			}
			
			if (moveRetractFeedrate != MOVE_RAPID) 
			{
				onLinearZ(safeDistance,moveRetractFeedrate);
				onLinearZ(retractDistance,MOVE_RAPID);
			}else
			{
				onLinearZ(retractDistance,moveRetractFeedrate);
			}

		}
	}
	else 
	{
	// Add all the cycle drilling operations here
		if (drillHeader.name == "Drilling G83")
		{
			// Move rapidly down to the safe distance
			onLinearZ(safeDistance,MOVE_RAPID);
			// Now drill to the end depth
			var g = gOutput.format(83);
			
			var z = zOutput.format(endDepth);
			var f = getFeedRate(movePlungingFeedrate);
			var p = pOutput.format(drillHeader.lowerDwell);

			if (!drillHeader.useLowerDwell) 
			{
				p = "";
			}

			writeBlock(g, z, f, p);
			g = gOutput.format(80);
			writeBlock(g);

			onLinearZ(retractDistance,MOVE_RAPID);
		}
		else if (drillHeader.name == "Tapping CW G84")
		{
			// Move rapidly down to the safe distance
			onLinearZ(safeDistance,MOVE_RAPID);

			// Calculate the moves to the end depth using pecking
			// An array will hold the depths for each peck
			// Move rapidly down to the safe distance
			onLinearZ(safeDistance,MOVE_RAPID);
			// Now drill to the end depth
			var g = gOutput.format(84);
			var z = zOutput.format(endDepth);
			var f = feedOutputTwoDecimals.format(drillHeader.pitch);
			writeBlock(g, z, f);
			g = gOutput.format(80);
			writeBlock(g);

			onLinearZ(retractDistance,MOVE_RAPID);

		}
	}
}

function onComment(text){
	var comment = commentFront + text + commentBack;

	writeBlock(comment); 
}

// Support function to use if only output in the zAxis is used
function onLinearZ(vz_,movement){
	// The xInternal and zInternal variables are used to keep track of the coordinates from CNC-Calc.
	// Since this is turning a shift in the coordinates: 
	// x in CNC-Calc becomes z in the post and y in CNC-Calc becomes x 
	var zInternal = vz_;

	if (movement == MOVE_RAPID) {
		var g = gOutput.format(0);
	} else {
		var g = gOutput.format(1);
	}
	
	var z = zOutput.format(zInternal);
	var f = getFeedRate(movement);
	var c = getCompensation();
	writeBlock(c, g, z, f);
}

function onLinear(vx_, vz_, movement) {
	// The xInternal and zInternal variables are used to keep track of the coordinates from CNC-Calc.
	// Since this is turning a shift in the coordinates: 
	// x in CNC-Calc becomes z in the post and y in CNC-Calc becomes x 
	var xInternal = vx_;
	var zInternal = vz_;

	
	
	var x = xOutput.format(xInternal);
	var z = zOutput.format(zInternal);

	if (x || z) 
	{
		if (movement == MOVE_RAPID) 
		{
			var g = gOutput.format(0);
		} else 
		{
			var g = gOutput.format(1);
		}

		var f = getFeedRate(movement);
		var c = getCompensation();
		writeBlock(c, g, x, z, f);
	}
}

function onCircular(cx, cz, ex, ez, isCW, movement) {
	var xCenterInternal = cx;
	var zCenterInternal = cz;
	var xEndInternal = ex;
	var zEndInternal = ez;
	
	// current position
	var lastX = xOutput.getLast();
	var lastZ = zOutput.getLast();
	
	// make i, j, k relative
	var i = xCenterInternal - lastX;
	var k = zCenterInternal - lastZ;

	if (globals.absoluteArcCenter) 
	{
		i = xCenterInternal;
		k = zCenterInternal;
	}

	var radius = Math.sqrt(((xCenterInternal - xEndInternal) * (xCenterInternal - xEndInternal)) + 
						   ((zCenterInternal - zEndInternal) * (zCenterInternal - zEndInternal)));	

	// feed rate
	var f = getFeedRate(movement);
	
	// distance to center has to be the same from start and end positions
	if (Math.abs(distance(lastX, lastZ, xCenterInternal, zCenterInternal) - distance(xEndInternal, zEndInternal, xCenterInternal, zCenterInternal)) > globals.tolerance) {
		throw new Error("Distance to center has to be the same from start and end positions");
	}
	
	// final position
	var x = xOutput.format(xEndInternal);
	var z = zOutput.format(zEndInternal);
	
	// center of circle
	i = iOutput.format(i);
	k = kOutput.format(k);
	
	// g code and compensation
	gOutput.reset();

	var gCode = 2;

	if (isCW) 
	{
		if (globals.xAxisFactor * globals.zAxisFactor > 0)
		{
			// Right hand coordinates system
			gCode = 2;
		}
		else 
		{
			// Left hand coordinate system
			gCode = 3;
		}
	}
	else
	{
		if (globals.xAxisFactor * globals.zAxisFactor > 0)
		{
			// Right hand coordinates system
			gCode = 3;
		}
		else 
		{
			// Left hand coordinate system
			gCode = 2;
		}
	}

	var g = gOutput.format(gCode);
	var c = getCompensation();
	
	if (globals.useRadius) 
	{
		var r = radiusOutput.format(radius);
		if (x || z) {
			writeBlock(c, g, x, z, r, f);
		}
	}
	else
	{
		if (x || z) {
			writeBlock(c, g, x, z, i, k, f);
		}
	}
}

function onCompensation(comp) {
	lastCompensation = comp;
}

function onDwell(seconds) {
	writeBlock(gOutput.format(4), dwellOutput.format(seconds));
}

// Not used in the lathe post
// function onDrillHeader(obj) {
// }

// Not used in the lathe post
// function onDrillPoint(x, y, z) {	
// }

// Not used in the lathe post
// function onDrillFooter() 
// {
// }

function setFeedrate(movement, feedRate) {
	feedRates[movement] = feedRate;
}

function getParameter(name) {
	if (! (name in propertyNames)) {
		throw new Error(name + " not a known property");
	}
	if (! (name in globals)) {
		throw new Error(name + " not yet set");
	}
	return globals[name];
}

function setParameter(name, value) {
	if (! (name in propertyNames)) {
		throw new Error(name + " not a known property");
	}
	globals[name] = value;
}

