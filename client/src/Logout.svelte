<script>
    import { logout_user } from './rest.js';
    import { logged_in } from './stores.js';

    let text = 'Logging out…';

    async function logout() {
        try {
            await logout_user();
        } catch (e) {
            text = `Error: ${e.message}. <a href="/logout">Try again</a>.`;
            return;
        }

        logged_in.set(false);
        window.location.replace('/login');
        text = `Logout success. <a href="/login">Login again</a>.`;
    }

    logout();
</script>

<p>{@html text}</p>
