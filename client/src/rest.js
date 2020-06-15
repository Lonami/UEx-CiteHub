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

async function fetch_json(resource, init) {
    const res = await fetch(resource, init);
    if (res.ok) {
        return await res.json();
    } else {
        throw new NetworkError(await res.text(), res.status);
    }
}

export function get_publications() {
    return fetch_json('/rest/publications');
}

export function get_profile() {
    return fetch_json('/rest/profile');
}

export function save_profile(data) {
    return fetch_json('/rest/profile', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}
