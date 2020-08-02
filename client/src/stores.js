import { writable } from 'svelte/store';

export const user_token = writable(localStorage.getItem('user_token'));

const unsubscribe = user_token.subscribe(value => {
    if (value === null) {
        localStorage.removeItem('user_token');
    } else {
        localStorage.setItem('user_token', value);
    }
});
