function response = isrunning(object)
% ISRUNNING checks if a serial or timer object is running/open or not

% error checking
narginchk(1, 1)

% checks the class and validity
if iscell(object)
    
    % recursively call this
    response = cellfun(@isrunning, object, 'UniformOutput', false);
    
elseif all(isserial(object))
    
    % dodgy work-around for if the realterm handle is being used
    
    % pre-allocates the answer
    response = false(size(object));
    
    % for each object (uses prod(size) since numel is not defined for
    % serial objects)
    for m = 1:prod(size(object))
        
        % does the user data contain the realterm handle?
        if isstruct(object(m).UserData) && isfield(object(m).UserData, 'realTermHandle') && isa(object(m).UserData.realTermHandle, 'COM.realterm_realtermintf')
            % then check the realterm handle
            response(m) = logical(object(m).UserData.realTermHandle.PortOpen);
            
        else
            
            % then check it conventionally
            response(m) = onoff(object(m).Status);
        end
    end
    
    % checks if it is running or not
    %response = onoff({object.Status});
    
elseif all(istimer(object))
    
    % checks if it is running or not (don't need to turn it into a cell
    % array because the timer does not need it - it is not a fully correct
    % implementation of structured objects (infuriatingly)
    response = onoff(object.Running);
    
elseif all(isa(object, 'COM.realterm_realtermintf'))
    
    % checks if its running or not
    response = logical([object.PortOpen]);

else
    
    % error as unknown class
    error('Only defined for valid serial and timer objects.')
end