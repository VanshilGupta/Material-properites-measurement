function serialObject = tempobj(comPort, userDataOrDeviceAddress)
% TEMPOBJ Returns the serial object for Eurotherm temperature controllers
% serialObject = tempobj(comPort, userDataOrDeviceAddress) returns the
% serial object for Eurotherm series 2000 temperature controllers given a
% suitable
% COM port number (unsigned integer: 1-255).  If an object already exists
% on that COM port (open or otherwise), returns an error.  Information can
% be passed into the serial object through the optional userData argument
% in the form of a structure only, or a deviceAddress can be specified, in
% which case this will be stored in a structure in the UserData with the
% field "deviceAddress".  The deviceAddress must be an integer in the 0-254
% range.

% e.g. serialObject = tempobj(7) - returns a serial object for the
% temperature controller on COM7

% e.g. 2 serialObject = tempobj(7, 3) - returns a serial object for the
% temperature controller on COM7, with the UserData being a structure only
% containing the field UserData.deviceAddress = 3.

% e.g. 3 userData.someData = rand; e.g. 3
% serialObject = tempobj(7, userData) returns a serial object with the
% UserData being a structure with a field of deviceAddress containing a
% random number.

% e.g. 4 userData.deviceAddress = 3; userData.someData = rand; e.g. 3
% serialObject = tempobj(7, userData) returns a serial object with the
% UserData being a structure with two fields containing the device address
% and some other data.


% defines a default device address
defaultDeviceAddress = 1;

% Error handling (number of arguments is checked this way for backwards
% compatibility with earlier versions of MATLAB)
error(nargchk(1, 2, nargin))

% checks the rest
if ~isnumeric(comPort) || ~isscalar(comPort) || comPort ~= uint8(comPort) || ~comPort
    % COM ports 1-255 allowed only
    error('comPort must be an unsigned integer from 1 to 255')

% if the optional argument is supplied, check it before we create the
% serial object
elseif nargin >= 2
    % is it a structure?
    if isstruct(userDataOrDeviceAddress)
        
        % if it contains useful data keep that for userData - this is not
        % ideal for large amounts of data in userData since this copies it
         userData = userDataOrDeviceAddress;% - shouldn't be an issue for the majority of applications though
       
        
        % does it contain the deviceAddress - we don't need modify it if it
        % does
        if isfield(userDataOrDeviceAddress, 'deviceAddress')
            
            % further check
            if ~isvalidtempobjdeviceaddress(userDataOrDeviceAddress.deviceAddress)
                % error - if its provided it should be the one to use, so
                % something is wrong
                error('Invalid deviceAddress field in UserData structure.')
            end
            
        else
            % define a default within the userData
            userData.deviceAddress = defaultDeviceAddress;
        end
        
    % was a deviceAddress supplied as a number?
    elseif isvalidtempobjdeviceaddress(userDataOrDeviceAddress)
        % then store that in userData
        userData.deviceAddress = userDataOrDeviceAddress;
        
    else
        % then a second argument was provided, but it was neither an
        % acceptable structure or a deviceAddress so something went wrong
        error('Invalid optional second argument - must be a structure or a valid device addreess.')
    end
    
    % by definition nargin == 1, so we need to define a default
else
    % define a default within the userData
    userData.deviceAddress = defaultDeviceAddress;
end

% if object on specified COM port exists, errors, otherwise creates
% serial object

% initialises variables
serialPort = sprintf('COM%d', comPort);

% if serial object does not exist, defines serial object and opens it
if isempty(instrfindall('Port', serialPort))
    serialObject = serial(  serialPort,...
        'BaudRate', 9600,...
        'DataBits', 8,...
        'Parity', 'none',...
        'StopBits', 1,...
        'Terminator', '',...
        'TimeOut', 0.5,...
        'UserData', userData);
    
else
    % errors
    error('Object(s) already exist on this serial port')
end
