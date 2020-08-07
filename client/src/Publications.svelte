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
        max-width: 1200px;
    }

    th {
        font-variant: small-caps;
        background-color: #eee;
        padding: 2px 4px;
        cursor: pointer;
    }
</style>

<div class="publications">
    {#await get_publications()}
        <p>Loading publications…</p>
    {:then result}
        <table>
            <thead>
                <tr>
                    <th on:click={_ => set_sort(null)}>Source</th>
                    <th on:click={_ => set_sort("name")}>Title</th>
                    <th on:click={_ => set_sort("cites")}>Cited by</th>
                    <th on:click={_ => set_sort("year")}>Year</th>
                </tr>
            </thead>
            <tbody>
                {#each sort_list(result.publications) as publication}
                    <Publication {publication}/>
                {/each}
            </tbody>
        </table>
    {:catch error}
        <p>Failed to fetch publications: {error.message}</p>
    {/await}
</div>
