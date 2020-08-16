<script>
    import { logged_in } from './stores.js';

    let is_logged;
    const unsubscribe = logged_in.subscribe(value => {
        is_logged = value;
        if (window.location.pathname === '/') {
            if (is_logged) {
                window.location.replace('/metrics');
            } else {
                window.location.replace('/login');
            }
        }
    });
</script>

<style>
nav {
    background-color: #005682 /* homestuck colors */;
    border-bottom: 5px solid #000;
}

ul {
    margin: 0;
    list-style-type: none;
    padding-left: 0;
    display: flex;
}

li {
    display: inline-block;
}

a {
    color: #fff;
    text-decoration: none;
    font-size: large;
    padding: 1em;
    transition: background-color 250ms;
    display: inline-block;
}

a:hover, a.selected {
    background-color: #008282;
}
</style>

<nav>
    <ul>
        <!-- Routes also in: App.svelte, server.py -->
        <li><a href='/' class:selected={window.location.pathname == '/a'}><strong>UEx CiteHub</strong></a></li>
        {#if is_logged}
            <li><a href='/metrics' class:selected={window.location.pathname == '/metrics'}>Metrics</a></li>
            <li><a href='/publications' class:selected={window.location.pathname == '/publications'}>Publications</a></li>
            <li><a href='/profile' class:selected={window.location.pathname == '/profile'}>Profile</a></li>
            <li><a href='/logout' class:selected={window.location.pathname == '/logout'}>Logout</a></li>
        {:else}
            <li><a href='/register' class:selected={window.location.pathname == '/register'}>Register</a></li>
            <li><a href='/login' class:selected={window.location.pathname == '/login'}>Login</a></li>
        {/if}
    </ul>
</nav>
