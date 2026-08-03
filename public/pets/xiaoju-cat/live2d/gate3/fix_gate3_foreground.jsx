#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

    var source = null;
    var master = null;
    for (var i = 0; i < doc.layers.length; i++) {
        if (doc.layers[i].name === "SRC_Planet_Foreground") source = doc.layers[i];
        if (doc.layers[i].name === "GATE3_RIG_PARTS") master = doc.layers[i];
    }
    if (!source || !master) return;

    var foreground = null;
    for (var j = 0; j < master.layerSets.length; j++) {
        if (master.layerSets[j].name === "06_FOREGROUND_OVERLAY") foreground = master.layerSets[j];
    }
    if (!foreground) return;

    for (var k = foreground.layers.length - 1; k >= 0; k--) {
        if (foreground.layers[k].name === "Planet_FrontRim") {
            foreground.layers[k].allLocked = false;
            foreground.layers[k].remove();
        }
    }

    var rim = source.duplicate();
    rim.allLocked = false;
    rim.name = "Planet_FrontRim";
    rim.move(foreground, ElementPlacement.INSIDE);
    rim.visible = true;
    doc.activeLayer = master;
    doc.save();
}());
