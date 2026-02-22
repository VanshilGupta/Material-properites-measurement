function serialwrite(serialObject, data, varargin)
% SERIALWRITE writes to a serial object depending on if it contains the
% Realterm handle or not.

% checks the number of arguments
narginchk(2, Inf)

% checks that a serial object has been passed
if ~isserial(serialObject)
    
    % errors
    error('Must supply a serial object.')
    
elseif (~isnumeric(data) && ~ischar(data)) || ~isvector(data)
    
    % the input must be a string
    error('Must send the data as a numeric vector.')
end

% finds if it should be realterm or not
if isfield(serialObject.UserData, 'realTermHandle')
    
    % checks the port is open
    if ~isrunning(serialObject.UserData.realTermHandle)
        % errors
        error('Realterm is not connected.')
    end

    % write it using real term
    realtermfwrite(serialObject.UserData.realTermHandle, data);
    
else
    
    % checks its connected
    if ~isrunning(serialObject)
        
        % errors
        error('Serial port is not open.')
    end
    
    % try-catched because of a known matlab issue
    try
        
        % send it conventionally
        fwrite(serialObject, data, varargin{:})
        
    catch
    end
end