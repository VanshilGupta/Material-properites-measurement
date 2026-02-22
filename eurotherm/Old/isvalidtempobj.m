function response = isvalidtempobj(serialObject)
% ISVALIDTEMPOBJ checks for suitablity of a serial object for tempobj_
% response = isvalidtempobj(serialObject) returns a scalar true or false
% for whether the serial object is a valid one or not for use with the
% tempobj_ suite of files.  Currently only accepts scalar objects, and
% features minimal checking but has been abstracted for possible future use
% with arrays.

% e.g. response = isvalidtempobj(tempobj(7)) will return true

% only simple comparison for now - by definition objects with a class
% 'serial' are scalar - arrays of serial objects are of class 'instrument'
response = (isa(serialObject, 'serial') && isvalid(serialObject));

% more strict checking is not in use, but is there for future use
% (currently only set up for scalars)
%if response
    % grabs user data
    %userData = serialObject.UserData;
    
    % checks for some required fields, then checks those further -
    % shortcircuiting prevents them from being checked if they're not there
    % in the first place
    %response = all(isfield(userData, {'deviceAddress', 'maxWords'})) && isvalidtempobjdeviceaddress(userData.deviceAddress) && isvalidtempobjmaxwords(userData.maxWords);
%end