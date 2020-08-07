<script>
    import Publication from './Publication.svelte';
    import Chart from './Chart.svelte';

    import { get_publications } from './rest.js';

    function explain_i_index(context) {
        let have = context.value !== '1' ? 's have' : 'has';
        return `${context.value} publication${have} ${context.label} or more citation`;
    }
</script>

<!-- TODO different endpoint -->
{#await get_publications()}
    <p>Loading metrics</p>
{:then result}
    <ul>
        <li>Publication count: <strong>{result.stats.pub_count}</strong></li>
        <li>
            Average of authors per publication:
            <strong title={result.stats.avg_author_count}>{result.stats.avg_author_count.toFixed(2)}</strong>
        </li>
        <li>e-index: <strong title={result.e_index}>{result.e_index.toFixed(2)}</strong></li>
        <li>g-index: <strong>{result.g_index}</strong></li>
        <li>h-index: <strong>{result.h_index}</strong></li>
        <Chart
            dataset_label="i-index" data={result.i_indices}
            x_label='Minimum citation count'
            y_label='Publication count'
            explanation_fn={explain_i_index} />
    </ul>
{:catch error}
    <p>Failed to fetch metrics: {error.message}</p>
{/await}
