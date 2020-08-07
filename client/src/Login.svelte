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
</script>

{#if error !== null}
    <p><strong>Error:</strong> {error.message}</p>
{/if}

{#if token_value === null}
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
{:else}
    <p>
        You're already logged in. If you want to register or login to another
        account you must <a href="/logout">logout</a> first.
    </p>
{/if}
