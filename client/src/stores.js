import { writable } from 'svelte/store';

// The token is a HttpOnly cookie which we can't access, but as long as we stay in sync this
// value will be correct (and if it's not the server will return forbidden on bad access).
export const logged_in = writable(JSON.parse(localStorage.getItem('logged_in') || "false"));

const unsubscribe = logged_in.subscribe(value => {
    localStorage.setItem('logged_in', JSON.stringify(value));
});
