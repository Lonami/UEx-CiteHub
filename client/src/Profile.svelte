<script>
import { onMount } from 'svelte';
import { get_user_profile, update_user_profile, update_password, delete_user } from './rest.js';
import { logged_in } from './stores.js';

let source_form;
let submit_source;

let password_form;
let submit_password;

let last_error = null;

let delete_confirm;

async function save_details() {
    submit_source.disabled = true;
    let old_submit = submit_source.value;
    submit_source.value = 'Saving…';
    try {
        let sources = {};
        for (let [source_key, value] of new FormData(source_form).entries()) {
            let [source, key] = source_key.split(".");
            if (sources[source] === undefined) {
                sources[source] = {};
            }
            sources[source][key] = value;
        }
        console.log(sources);
        let result = await update_user_profile(sources);
        if (result.errors.length !== 0) {
            let error = 'Some errors occured:';
            for (let e of result.errors) {
                error += `\nFailed to update ${e.source}.${e.key}: ${e.reason}`;
            }
            last_error = {message: error};
        }
    } catch (e) {
        last_error = e;
    } finally {
        submit_source.disabled = false;
        submit_source.value = old_submit;
    }
}

async function save_password() {
    // TODO reusable Form component that does this? (and disables all other fields)
    // TODO maybe move reusable components to components/ and pages to pages/
    submit_password.disabled = true;
    let old_submit = submit_source.value;
    submit_password.value = 'Updating…';
    try {
        await update_password(
            event.target.old_password.value,
            event.target.new_password.value
        );
        last_error = null;
    } catch (e) {
        last_error = e;
    } finally {
        submit_password.disabled = false;
        submit_password.value = old_submit;
    }
}

async function delete_account() {
    try {
        await delete_user();
        logged_in.set(false);
        window.location.replace('/');
    } catch (e) {
        last_error = e;
    }
}
</script>

<style>
    div.main {
        padding: 1em;
    }
</style>

{#if last_error !== null}
    <p>An error occured: {last_error.message}</p>
{/if}

<div class="main">
    {#await get_user_profile()}
        <p>Loading external source fields…</p>
    {:then profile}
        <p>Logged in as <em>{profile.username}</em>.</p>

        <h2>Sources</h2>
        <form bind:this={source_form} on:submit|preventDefault={save_details}>
            {#each Object.entries(profile.sources) as [source, fields]}
                <fieldset>
                    <legend>{source}</legend>
                    {#each Object.entries(fields) as [key, value]}
                        <div>
                            <label for="{source}.{key}">Value for {key}:</label>
                            <input id="{source}.{key}" name="{source}.{key}" value={value.value}>
                            <p>{@html value.description}</p>
                        </div>
                    {/each}
                </fieldset>
            {/each}
            <div>
                <input bind:this={submit_source} type="submit" value="Update sources">
            </div>
        </form>
    {:catch e}
        <p>Failed to load external source fields: {e.message}</p>
    {/await}

    <h2>Update password</h2>
    <form bind:this={password_form} on:submit|preventDefault={save_password}>
        <div>
            <label for="old_password">Old password: </label>
            <input type="password" name="old_password" id="old_password" required>
        </div>
        <div>
            <label for="new_password">New password: </label>
            <input type="password" name="new_password" id="new_password" required>
        </div>
        <div>
            <input bind:this={submit_password} type="submit" value="Update password">
        </div>
    </form>

    <h2>Export data</h2>

    <p>
        You may export all of your data as a compressed ZIP file consisting of several
        comma-separated values files (CSV) at any time. Please be considerate and don't
        abuse this feature, as it requires a fair amount of work on the server.
    </p>

    <form method="GET" action="/rest/takeout">
        <input type="submit" value="Export my data">
    </form>

    <h2>Delete account</h2>

    <p>
        After deleting your account, all of the retrieved data associated with it will be lost.
        If you're certain this is what you want, type "confirm" without quotes in the text box
        below and then click the button.
    </p>

    <form on:submit|preventDefault={delete_account}>
        <div>
            <label for="confirm">Confirmation: </label>
            <input type="text" name="confirm" id="confirm" bind:value={delete_confirm} required>
        </div>
        <div>
            <input type="submit" value="Delete account" disabled={delete_confirm != "confirm"}>
        </div>
    </form>
</div>
