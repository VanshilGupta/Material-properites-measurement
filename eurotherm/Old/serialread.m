function output = serialread(serialObject, varargin)
% SERIALREAD reads from a serial object depending on if it contains the
% Realterm handle or not.

% checks the number of arguments
narginchk(1, Inf)

% checks that a serial object has been passed
if ~isserial(serialObject)
    
    % errors
    error('Must supply a serial object.')
end

% finds if it should be realterm or not
if isfield(serialObject.UserData, 'realTermHandle')
    
    % checks the rest of the fields are there
    if ~isfield(serialObject.UserData, 'captureFileID')
        
        % errors
        error('Cannot retrieve the capture file ID.')
        
    elseif ~isrunning(serialObject.UserData.realTermHandle)
        
        % errors
        error('Realterm is not connected.')
    end
    
    % read it in using real term (assumes the timeout on the serial object
    % has been set up correctly)
    output = realtermfread( serialObject.UserData.realTermHandle,...
                            serialObject.UserData.captureFileID,...
                            serialObject.TimeOut,...
                            varargin{:});
    
else
    
    % checks its connected
    if ~isrunning(serialObject)
        
        % errors
        error('Serial port is not open.')
    end
    
    % seem to get some strange moaning if the varargin{:} is used with
    % fread
    if nargin == 1
        
        % read it out
        output = fread(serialObject);

    else
        
        % read it in conventionally
        output = fread(serialObject, varargin{:});
    end
end