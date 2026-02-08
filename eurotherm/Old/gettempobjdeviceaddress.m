function deviceAddress = gettempobjdeviceaddress(serialObject)
% GETTEMPOBJDEVICEADDRESS retrieves a device address from a tempobj object
% deviceAddress = gettempobjdeviceaddress(serialObject) attempts to
% retrieve a deviceAddress from a "deviceAddress" field in a structure in
% the UserData, returning 1 if no device is specified.  This is present to
% ensure backwards compatibility.

% grab user data
userData = serialObject.UserData;

% evaluates that (isfield also checks for suitability as a structure)
if isfield(userData, 'deviceAddress')
    % sets that as the deviceAddress (assuming its OK - not worth
    % checking every single time as if this isn't valid then something
    % else is up)
    deviceAddress = userData.deviceAddress;

else
    % specifies the default
    deviceAddress = 1;
end