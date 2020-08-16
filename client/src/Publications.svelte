<script>
    import Publication from './Publication.svelte';
    import Chart from './Chart.svelte';

    import { get_publications } from './rest.js';

    let sort_by = {key: null, rev: false};
    function set_sort(key) {
        if (sort_by.key === key) {
            sort_by.rev = !sort_by.rev;
        } else {
            sort_by = {key: key, rev: false};
        }
    }

    $: sort_list = function(items) {
        if (sort_by.key === null) {
            return items;
        } else {
            let value = sort_by.rev ? -1 : 1;
            let sorted = items.slice();
            sorted.sort(function(a, b) {
                if (a[sort_by.key] < b[sort_by.key]) {
                    return -value;
                } else if (a[sort_by.key] > b[sort_by.key]) {
                    return value;
                } else {
                    return 0;
                }
            });
            return sorted;
        }
    }
</script>

<style>
    table {
        border-collapse: collapse;
        width: 100%;
    }

    th {
        font-variant: small-caps;
        background-color: #eee;
        padding: 0.5em 1em;
        cursor: pointer;
        font-size: large;
    }
</style>

{#await get_publications()}
    <p>Loading publications…</p>
{:then publications}
    <table>
        <thead>
            <tr>
                <th on:click={_ => set_sort(null)} title="Where this publication has been found in">Source</th>
                <th on:click={_ => set_sort("name")} title="Title of the publication">Title</th>
                <th on:click={_ => set_sort("cites")} title="Amount of unique cites the publication has">Cited by</th>
                <th on:click={_ => set_sort("year")} title="Year when the publication was published">Year</th>
            </tr>
        </thead>
        <tbody>
            {#each sort_list(publications) as publication}
                <Publication {publication}/>
            {/each}
        </tbody>
    </table>
{:catch error}
    <p>Failed to fetch publications: {error.message}</p>
{/await}
