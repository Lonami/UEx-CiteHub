import { user_token } from './stores.js';

let token;
const unsubscribe = user_token.subscribe(value => {
    token = value;
});

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
    if (token !== null) {
        init = init || {};
        init['headers'] = init['headers'] || {};
        init['headers']['Authorization'] = token;
    }
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

export function get_sources() {
    return fetch_json('/rest/sources');
}

export function save_sources(data) {
    return fetch_json('/rest/sources', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

export function force_merge() {
    return fetch_json('/rest/force-merge', {method: 'POST'});
}

export function register_user(username, password) {
    return fetch_json('/rest/user/register', {
        method: 'POST',
        body: JSON.stringify({
            username,
            password
        })
    });
}

export function login_user(username, password) {
    return fetch_json('/rest/user/login', {
        method: 'POST',
        body: JSON.stringify({
            username,
            password
        })
    });
}

export function logout_user() {
    return fetch_json('/rest/user/logout', {
        method: 'POST'
    });
}

export function delete_user() {
    return fetch_json('/rest/user/delete', {
        method: 'POST'
    });
}
