function NetworkError(message, status) {
    var instance = new Error(message);
    instance.name = 'NetworkError';
    instance.status = status;
    Object.setPrototypeOf(instance, Object.getPrototypeOf(this));
    if (Error.captureStackTrace) {
        Error.captureStackTrace(instance, NetworkError);
    }
    return instance;
}

NetworkError.prototype = Object.create(Error.prototype, {
    constructor: {
        value: Error,
        enumerable: false,
        writable: true,
        configurable: true
    }
});
Object.setPrototypeOf(NetworkError, Error);

async function query(endpoint) {
    const res = await fetch(endpoint, {
        // "To automatically send cookies for the current domain, this option must be provided."
        // https://developer.mozilla.org/en-US/docs/Web/API/WindowOrWorkerGlobalScope/fetch
        // Further reading: https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials
        credentials: 'include'
    });
    if (res.ok) {
        return await res.json();
    } else {
        throw new NetworkError(await res.text(), res.status);
    }
}

export function get_publications() {
    return query('/rest/publications');
}
