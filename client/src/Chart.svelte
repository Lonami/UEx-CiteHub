<script>
    import Chart from 'chart.js';
    import { onMount } from 'svelte';

    export let y_label;
    export let x_label;
    export let dataset_label;
    export let data;
    export let explanation_fn;

    let canvas;
    onMount(() => {
        // TODO not sure if doing labels like this is the right way
        let labels = [];
        data.forEach(function (datum, index) {
            labels.push(`${index + 1}`);
        });
        var myChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: dataset_label,
                    data,
                }]
            },
            options: {
                tooltips: {
                    callbacks: {
                        title: function() { return ''; },
                        label: explanation_fn
                    }
                },
                scales: {
                    xAxes: [{
                        display: true,
                        scaleLabel: {
                            display: true,
                            labelString: x_label
                        }
                    }],
                    yAxes: [{
                        display: true,
                        scaleLabel: {
                            display: true,
                            labelString: y_label
                        }
                    }]
                }
            }
        });
    });
</script>

<style>
    .chart-container {
        position: relative;
        height: 40vh;
        width: 80vw;
    }
</style>

<!-- Need parent div so that the canvas can be responsive -->
<div class="chart-container">
    <canvas bind:this={canvas} aria-label='Chart' role='img'>
        <table>
            <caption>{dataset_label}</caption>
            <thead>
                <tr>
                    <th scope='col'>{x_label}</th>
                    <th scope='col'>{y_label}</th>
                </tr>
            </thead>
            <tbody>
                {#each data as datum, i}
                    <tr>
                        <td>{i + 1}</td>
                        <td>{datum}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    </canvas>
</div>
