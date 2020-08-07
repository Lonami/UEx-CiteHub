<script>
import { onMount } from 'svelte';
import { get_user_profile, update_user_profile, update_password, force_merge } from './rest.js';

let source_form;
let submit_source;

let password_form;
let submit_password;

let last_error = null;

async function save_details() {
    submit_source.disabled = true;
    let old_submit = submit_source.value;
    submit_source.value = 'Saving…';
    try {
        let data = {}
        for (let [key, value] of new FormData(source_form).entries()) {
            data[key] = value;
        }
        let result = await update_user_profile(data);
        if (result.errors.length !== 0) {
            let error = 'Some errors occured:';
            for (let e of result.errors) {
                error += `\nFailed to update ${e.namespace}.${e.key}: ${e.reason}`;
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
</script>

<style>
</style>

{#if last_error !== null}
    <p>An error occured: {last_error.message}</p>
{/if}

<button on:click={force_merge}>Force merge</button>

<h2>Sources</h2>
{#await get_user_profile()}
    <p>Loading external source fields…</p>
{:then profile}
    <p>Logged in as <em>{profile.username}</em>.</p>
    <form bind:this={source_form} on:submit|preventDefault={save_details}>
        {#each profile.sources as source}
            <div>
                <label for="es-{source.key}">Value for {source.key}:</label>
                <input id="es-{source.key}" name={source.key} value={source.value}>
                <p>{@html source.description}</p>
            </div>
        {/each}
        <div>
            <input bind:this={submit_source} type="submit" value="Save">
        </div>
    </form>
    <!-- TODO allow deleting account (including all its downloaded sources) -->
{:catch e}
    <p>Failed to load external source fields: {e.message}</p>
{/await}

<h2>Update password</h2>
<form>
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
</form>
