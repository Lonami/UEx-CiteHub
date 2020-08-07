<script>
    import { user_token } from './stores.js';

    let token;
	const unsubscribe = user_token.subscribe(value => {
        token = value;
        if (window.location.pathname === '/') {
            if (token === null) {
                window.location.replace('/login');
            } else {
                window.location.replace('/metrics');
            }
        }
	});
</script>

<style>
nav {
    border-bottom: 1px solid #000;
}

ol {
    list-style-type: none;
    padding-left: 0;
}

li {
    display: inline-block;
}

a::after {
    display: inline-block;
    color: #000;
    content: '»';
    font-size: 80%;
    font-weight: bold;
    padding: 0 3px;
}

.selected {
    font-weight: bold;
}
</style>

<nav>
    <ol>
        <!-- Routes also in: App.svelte, server.py -->
        <li><a href='/' class:selected={window.location.pathname == '/'}>UEx CiteHub</a></li>
        {#if token === null}
            <li><a href='/register' class:selected={window.location.pathname == '/register'}>Register</a></li>
            <li><a href='/login' class:selected={window.location.pathname == '/login'}>Login</a></li>
        {:else}
            <li><a href='/metrics' class:selected={window.location.pathname == '/metrics'}>Metrics</a></li>
            <li><a href='/publications' class:selected={window.location.pathname == '/publications'}>Publications</a></li>
            <li><a href='/profile' class:selected={window.location.pathname == '/profile'}>Profile</a></li>
            <li><a href='/logout' class:selected={window.location.pathname == '/logout'}>Logout</a></li>
        {/if}
    </ol>
</nav>
