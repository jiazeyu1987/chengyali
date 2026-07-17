const settingsButton = document.querySelector("#settings-button");
const settingsDialog = document.querySelector("#settings-dialog");

if (settingsButton && settingsDialog) {
  settingsButton.addEventListener("click", () => settingsDialog.showModal());

  settingsDialog
    .querySelectorAll(".settings-dialog-close")
    .forEach((button) => button.addEventListener("click", () => settingsDialog.close()));

  settingsDialog.addEventListener("click", (event) => {
    if (event.target === settingsDialog) {
      settingsDialog.close();
    }
  });
}
