function output = serialflush(serialObject, varargin)
% SERIALFLUSH reads from a serial object depending on if it contains the
% Realterm handle or not.

% checks the number of arguments
narginchk(1, Inf)

% checks that a serial object has been passed
if ~isserial(serialObject)
    
    % errors
    error('Must supply a serial object.')
end

% if the size is supplied, change it to Inf to read out everything, while
% still allowing the use of the precision argument
if nargin >= 2
    
    % set it to inf
    varargin{1} = Inf;
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
    
    % read everything out
    output = fread(serialObject.UserData.captureFileID, varargin{:});
    
else
    % checks its connected
    if ~isrunning(serialObject)
        
        % errors
        error('Serial port is not open.')
    end
    
    % if there is some data to flush
    if serialObject.BytesAvailable
        
        % if there's some arguments...
        if nargin > 1
            
            % read it out conventionally
            output = fread(serialObject, varargin{:});

        else
            
            % read out all the bytes
            output = fread(serialObject, serialObject.BytesAvailable);
        end
        
        % if flow control is on, then the buffer will be filled, but MATLAB
        % will not ask for more data until the buffer has been emptied - it
        % takes a short amount of time for the buffer to refill again
        if ~strcmp(serialObject.FlowControl, 'none')
            
            % need to allow a short pause to fill the buffer - this is
            % difficult to determine - currently set to use either the
            % TimeOut setting, or 0.1 seconds, depending on which one is
            % the smallest) - this could definitely be improved upon
            pause(min(0.1, serialObject.TimeOut))
            
            % if there's still some data in there, then the serial object may
            % be under flow control so that it is holding back data (no such
            % issues with the Realterm buffer)
            if serialObject.BytesAvailable
                
                % recursively call it until there's nothing left
                output = [output; serialflush(serialObject, varargin{:})];
            end
        end
        
    else
        
        % return something empty
        output = [];
    end
end