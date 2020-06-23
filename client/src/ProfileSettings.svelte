<script>
import { onMount } from 'svelte';
import { get_sources, save_sources } from './rest.js';

let scholar_input;
let academics_input;

let submit_button;

$: form_inputs = [
    scholar_input,
    academics_input,
];

let last_error = null;

async function init() {
    try {
        let sources = await get_sources();

        form_inputs.forEach(input => {
            input.value = sources[input.name];
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
        let sources = {};
        form_inputs.forEach(input => {
            sources[input.name] = input.value;
        });
        await save_sources(sources);
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
        <input bind:this={scholar_input} id="gs-profile-url" name="gs-profile-url" type="url" placeholder="https://scholar.google.com/citations?user=XK_M4ZsAAAAJ" disabled>
        <p>
            Help: navigate to <a href="https://scholar.google.com/citations?view_op=search_authors">Google Scholar's profiles search</a>
            and search for your profile. Click on it when you find it and copy the URL.
        </p>
    </div>
    <div>
        <label for="msacademics-profile-url">Microsoft Academics name and institution:</label>
        <input bind:this={academics_input} id="msacademics-profile-url" name="msacademics-profile-url" type="text" placeholder="https://academic.microsoft.com/profile/09f41163-0628-4f55-bf51-221cd6704a4f/FullName" disabled>
        <p>
            Help: navigate to <a href="https://academic.microsoft.com/home">Microsoft Academic's home</a>
            and search for your profile. Click on it when you find it and copy the URL.
        </p>
    </div>
    <div>
        <input bind:this={submit_button} type="submit" value="Save">
    </div>
</form>
