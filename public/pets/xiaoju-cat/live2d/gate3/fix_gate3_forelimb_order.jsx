#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    var master = null;
    for (var i = 0; i < doc.layers.length; i++) {
        if (doc.layers[i].name === "GATE3_RIG_PARTS") master = doc.layers[i];
    }
    if (!master) return;
    var foreground = null;
    var arms = null;
    for (var j = 0; j < master.layerSets.length; j++) {
        if (master.layerSets[j].name === "06_FOREGROUND_OVERLAY") foreground = master.layerSets[j];
        if (master.layerSets[j].name === "05_FORELIMBS_JOINTED") arms = master.layerSets[j];
    }
    if (!foreground || !arms) return;
    arms.move(foreground, ElementPlacement.PLACEAFTER);
    doc.activeLayer = master;
    doc.save();
}());
