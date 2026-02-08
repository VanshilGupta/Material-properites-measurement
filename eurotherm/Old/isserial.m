function response = isserial(serialObject)
% ISSERIAL checks if an object is a valid serial object

% checks the number of arguments
narginchk(1, 1)

% if its a structure, error
if isstruct(serialObject)
    % errors
    error('Not defined for structures.')
end

% different tests for different types
if iscell(serialObject)
    % recursively call this function
    response = cellfun(@isserial, serialObject, 'UniformOutput', false);
    
else
    % if it is a serial object (by definition a 1x1 serial object)
    if isa(serialObject, 'serial');
        % checks the serial object for validity
        response = isvalid(serialObject);
    
    % a serial object that is larger than 1x1 becomes an instrument object
    % BUT this can include a host of other instrument objects e.g. tcpip
    % etc. etc....which may also be scalar so this ends up in a recursion
    % loop otherwise
    elseif ~isscalar(serialObject) && isa(serialObject, 'instrument');
        % pre-defines the answer
        response = false(size(serialObject));
        
        % apply recursively on to each item
        for m = 1:numel(serialObject)
            % tests each item - the class of a collection of things
            % (serial, tcpip, etc.) is 'instrument', but individually they
            % are still serial or tcpip etc.
            response(m) = isserial(serialObject(m));
        end
        
    else
        % generates a false response the same size as the serialObject
        response = false(size(serialObject));
    end
end