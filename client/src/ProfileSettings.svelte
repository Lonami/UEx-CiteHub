<script>
import { onMount } from 'svelte';
import { get_profile, save_profile } from './rest.js';

let scholar_input;
let submit_button;

$: form_inputs = [
    scholar_input
];

let last_error = null;

async function init() {
    try {
        let profile = await get_profile();

        form_inputs.forEach(input => {
            input.value = profile[input.name];
        });
    } catch (e) {
        last_error = e;
    } finally {
        form_inputs.forEach(input => {
            input.disabled = false;
        });
    }
}

async function save_details() {
    submit_button.disabled = true;
    submit_button.value = 'Saving…';
    try {
        let data = {};
        form_inputs.forEach(input => {
            data[input.name] = input.value;
        });
        await save_profile(data);
    } catch (e) {
        last_error = e;
    } finally {
        submit_button.disabled = false;
        submit_button.value = 'Save';
    }
}

onMount(init);
</script>

<style>
</style>

{#if last_error !== null}
    <p>An error occured: {last_error.message}</p>
{/if}

<form on:submit|preventDefault={save_details}>
    <div>
        <label for="gs-profile-url">Google Scholar profile URL:</label>
        <input bind:this={scholar_input} id="gs-profile-url" name="gs-profile-url" type="url" disabled>
        <p>
            Help: navigate to <a href="https://scholar.google.com/citations?view_op=search_authors">Google Scholar's profiles search</a>
            and search for your profile. Click on it when you find it and copy the URL.
        </p>
    </div>
    <div>
        <input bind:this={submit_button} type="submit" value="Save">
    </div>
</form>
