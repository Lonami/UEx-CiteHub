<script>
   async function handle_submit(event) {
        console.log(event);
        console.log(event.target);
        console.log(event.target.username.value);
        console.log(event.target.password.value);
    }
</script>

<form on:submit|preventDefault={handle_submit}>
    <div>
        <label for="username">Username: </label>
        <input type="text" name="username" id="username" required>
    </div>
    <div>
        <label for="password">Password: </label>
        <input type="password" name="password" id="password" required>
    </div>
    <div>
        <input type="submit" value="Register">
    </div>
</form>
