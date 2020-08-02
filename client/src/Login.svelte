<script>
    import { register_user, login_user } from './rest.js';
    import { user_token } from './stores.js';

    export let register;

    let token_value;
	const unsubscribe = user_token.subscribe(value => {
		token_value = value;
	});

    let form;
    let error = null;

    function set_form_enabled(enabled) {
        for (let input of form.getElementsByTagName('input')) {
            input.disabled = !enabled;
        }
    }

    async function handle_submit(event) {
        set_form_enabled(false);

        let token = null;
        try {
            if (register) {
                token = await register_user(
                    event.target.username.value,
                    event.target.password.value
                );
            } else {
                token = await login_user(
                    event.target.username.value,
                    event.target.password.value
                )
            }
        } catch (e) {
            error = e;
            return;
        } finally {
            set_form_enabled(true);
        }

        user_token.set(token);
        window.location.replace('/metrics');
    }

    // TODO check if token_value is valid on non-register and skip auto-redirect
    // TODO what to do on login and register? a token would be "lost", maybe show a message logout before register
</script>

{#if error !== null}
    <p><strong>Error:</strong> {error.message}</p>
{/if}

<form bind:this={form} on:submit|preventDefault={handle_submit}>
    <div>
        <label for="username">Username: </label>
        <input type="text" name="username" id="username" required>
    </div>
    <div>
        <label for="password">Password: </label>
        <input type="password" name="password" id="password" required>
    </div>
    <div>
        <input type="submit" value={register ? "Register" : "Login"}>
    </div>
</form>
