import { logged_in } from './stores.js';

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
        if (res.status === 403) {
            // Not the best place to do this, but it's the most convenient.
            // Avoids having to check for status 403 everywhere a network call is made.
            logged_in.set(false);
            window.location.replace('/login');
        }

        throw new NetworkError(await res.text(), res.status);
    }
}

export function get_metrics() {
    return fetch_json('/rest/metrics');
}

export function get_publications() {
    return fetch_json('/rest/publications');
}

export function get_user_profile() {
    return fetch_json('/rest/user/profile');
}

export function update_user_profile(data) {
    return fetch_json('/rest/user/profile', {
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

export function update_password(old_password, new_password) {
    return fetch_json('/rest/user/update-password', {
        method: 'POST',
        body: JSON.stringify({
            old_password,
            new_password
        })
    });
}
