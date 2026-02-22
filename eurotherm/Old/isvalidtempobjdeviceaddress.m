function response = isvalidtempobjdeviceaddress(deviceAddress, parameter)
% ISVALIDTEMPOBJDEVICEADDRESS checks if a valid Modbus device address
% response = isvaliddeviceaddress(deviceAddress) returns a true or false
% scalar whether or not the deviceAddress is any scalar from 0-254
% ('loose'). parameter is an optional parameter a string of 'loose',
% 'spec', 'uint8', or 'strict' with a default of 'loose'.  For 'spec',
% there is an additional check for <247, since this is the official spec
% for modbus, although devices frequently ignore this.  'uint8' checks for
% 'uint8' as a datatype, and 'strict' checks for both of these properties.

% Example
% tf = isvaliddeviceaddress(double(7)) gives tf = true
% tf = isvaliddeviceaddress(NaN) gives tf = false
% tf = isvaliddeviceaddress(double(7), 'loose') gives tf = true
% tf = isvaliddeviceaddress(double(254), 'uint8') gives tf = false
% tf = isvaliddeviceaddress(254, 'spec') gives tf = false
% tf = isvaliddeviceaddress(uint8(1), 'strict') gives tf = true


% checks number of arguments
error(nargchk(1, 2, nargin))

% specify a parameter if one wasn't specified - default is loose
if nargin == 1
    % specify
    parameter = 'loose';

% last case is implied to be nargin == 2 so don't need to explicitly check
% - errors if the parameter is none of these things
% acts like (any([0, 0, 0, 0]) == 0))
elseif ~any(strcmp(parameter, {'loose', 'spec', 'uint8', 'strict'}))
    
    % errors
    error('Valid parameters are "spec", "uint8" and "strict" only')
end

% simple check for all - must be a scalar
if isscalar(deviceAddress)
    
    % different checks are faster in different orders
    switch parameter
        
        % simplifying and merging these would then require additional
        % checks and loss of ability to shortcircuit comparisons
        case 'loose'
            
            % must be numeric data type, is real, within the 0-254 range
            % (this returns false for NaN's), and must be an integer
            response = (isnumeric(deviceAddress) && isreal(deviceAddress) && deviceAddress >= 0 && deviceAddress <= 254 && deviceAddress == round(deviceAddress));

        case 'spec'
                
            % must be numeric data type, is real, within the 0-247 range
            % (this returns false for NaN's), and must be an integer
            response = (isnumeric(deviceAddress) && isreal(deviceAddress) && deviceAddress >= 0 && deviceAddress <= 247 && deviceAddress == round(deviceAddress));
                
        case 'uint8'
            
            % must be uint8 - doesn't need the explicit imaginary and integer check anymore
            response = (isa(deviceAddress, 'uint8') && deviceAddress >= 0 && deviceAddress <= 254);
            
        case 'strict'
            
            % must be also be <= 247
            response = (isa(deviceAddress, 'uint8') && deviceAddress >= 0 && deviceAddress <= 247);
    end

else
    % its not a scalar and is therefore invalid for all cases
    response = false;
end