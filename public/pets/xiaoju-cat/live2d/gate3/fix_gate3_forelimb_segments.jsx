#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

    function findTop(name) {
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === name) return doc.layers[i];
        }
        return null;
    }

    function findGroup(parent, name) {
        for (var i = 0; i < parent.layerSets.length; i++) {
            if (parent.layerSets[i].name === name) return parent.layerSets[i];
        }
        return null;
    }

    function unlockTree(container) {
        for (var i = 0; i < container.layers.length; i++) {
            if (container.layers[i].typename === "LayerSet") unlockTree(container.layers[i]);
            try { container.layers[i].allLocked = false; } catch (ignored) {}
        }
    }

    function selectPolygon(points) {
        var region = [];
        for (var i = 0; i < points.length; i++) {
            region.push([UnitValue(points[i][0], "px"), UnitValue(points[i][1], "px")]);
        }
        doc.selection.select(region, SelectionType.REPLACE, 0, false);
    }

    function slice(source, parent, name, points) {
        var layer = source.duplicate();
        layer.allLocked = false;
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        doc.activeLayer = layer;
        selectPolygon(points);
        doc.selection.invert();
        doc.selection.clear();
        doc.selection.deselect();
        return layer;
    }

    function whole(source, parent, name) {
        var layer = source.duplicate();
        layer.allLocked = false;
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        return layer;
    }

    function build(source, cover, parent, side, p) {
        slice(source, parent, "UpperArm_" + side, p.upper);
        slice(source, parent, "Elbow_Fur_" + side, p.elbow);
        slice(source, parent, "Forearm_" + side, p.forearm);
        slice(source, parent, "Wrist_Fur_" + side, p.wrist);
        slice(source, parent, "Paw_" + side, p.paw);
        whole(cover, parent, "Shoulder_Fill_" + side);
    }

    var master = findTop("GATE3_RIG_PARTS");
    var foreground = master ? findGroup(master, "06_FOREGROUND_OVERLAY") : null;
    var old = master ? findGroup(master, "05_FORELIMBS_JOINTED") : null;
    if (!master || !foreground || !old) return;
    unlockTree(old);
    old.allLocked = false;
    old.remove();

    var armL = findTop("SRC_Foreleg_L_Complete");
    var armR = findTop("SRC_Foreleg_R_Complete");
    var coverL = findTop("SRC_Shoulder_Occluder_L");
    var coverR = findTop("SRC_Shoulder_Occluder_R");
    if (!armL || !armR || !coverL || !coverR) return;

    var arms = master.layerSets.add();
    arms.name = "05_FORELIMBS_JOINTED";
    build(armL, coverL, arms, "L", {
        upper: [[400,650],[610,590],[670,780],[610,940],[430,950],[380,790]],
        elbow: [[410,545],[640,510],[690,700],[610,800],[400,715]],
        forearm: [[445,420],[690,390],[715,610],[625,700],[420,585]],
        wrist: [[500,350],[715,330],[730,515],[625,585],[480,485]],
        paw: [[535,320],[725,320],[740,480],[625,535],[515,435]]
    });
    build(armR, coverR, arms, "R", {
        upper: [[930,625],[1110,590],[1140,785],[1060,900],[900,820]],
        elbow: [[900,520],[1100,500],[1140,690],[1060,770],[885,670]],
        forearm: [[870,410],[1075,395],[1115,590],[1040,670],[855,555]],
        wrist: [[840,350],[1035,340],[1085,510],[1010,575],[835,470]],
        paw: [[820,325],[1015,325],[1050,475],[965,525],[815,430]]
    });

    // Keep the foreground planet above the newly rebuilt arm group.
    arms.move(foreground, ElementPlacement.PLACEAFTER);
    doc.activeLayer = master;
    doc.save();
}());
