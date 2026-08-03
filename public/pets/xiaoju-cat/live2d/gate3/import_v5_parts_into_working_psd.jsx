#target photoshop

(function () {
    if (!app.documents.length) return;
    var target = app.activeDocument;
    if (target.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

    var rootPath = "D:/CodeWorkspace/电脑桌宠/public/pets/xiaoju-cat/live2d/gate3/parts-v5/";

    function findTopLevel(name) {
        for (var i = 0; i < target.layers.length; i++) {
            if (target.layers[i].name === name) return target.layers[i];
        }
        return null;
    }

    function removeTopLevel(name) {
        var old = findTopLevel(name);
        if (old) {
            old.allLocked = false;
            old.remove();
        }
    }

    function subgroup(parent, name) {
        var group = parent.layerSets.add();
        group.name = name;
        return group;
    }

    function importLayer(filename, parent, visible) {
        var file = File(rootPath + filename);
        if (!file.exists) throw new Error("Missing Gate 3 part: " + file.fsName);
        var sourceDoc = app.open(file);
        var layer = sourceDoc.activeLayer.duplicate(target, ElementPlacement.PLACEATBEGINNING);
        sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument = target;
        layer.name = file.name.replace(/\.png$/i, "");
        layer.move(parent, ElementPlacement.INSIDE);
        layer.visible = visible;
        return layer;
    }

    removeTopLevel("GATE3_V5_IMPORT_TRIAL");
    var master = target.layerSets.add();
    master.name = "GATE3_V5_IMPORT_TRIAL";

    var body = subgroup(master, "02_BODY_VOLUME_ZONES");
    var hind = subgroup(master, "03_HINDLIMBS");
    var fore = subgroup(master, "04_FORELIMBS_SEGMENTED");
    var identity = subgroup(master, "05_APPROVED_IDENTITY");
    var eyes = subgroup(master, "06_EYES_GAZE_BLINK");
    var safety = subgroup(master, "99_COMPLETE_LIMB_SAFETY_HIDDEN");

    // Bottom-to-top import order. Hidden base remains as rollback material;
    // the independent volume zones are the intended Cubism bind surfaces.
    importLayer("10_Body_HiddenBase_v5.png", body, false);
    importLayer("13_Pelvis_Hidden_v5.png", body, true);
    importLayer("11_Ribcage_Hidden_v5.png", body, true);
    importLayer("12_Belly_Hidden_v5.png", body, true);

    importLayer("42_HindLeg_Far_v5_INFERRED.png", hind, false);
    importLayer("43_HindPaw_Far_v5_INFERRED.png", hind, false);
    importLayer("47_Hip_Far_v5_INFERRED.png", hind, false);
    importLayer("48_Thigh_Far_v5_INFERRED.png", hind, false);
    importLayer("49_Hock_Far_v5_INFERRED.png", hind, false);
    importLayer("44_Hip_Near_v5.png", hind, true);
    importLayer("45_Thigh_Near_v5.png", hind, true);
    importLayer("46_Hock_Near_v5.png", hind, true);
    importLayer("41_HindPaw_Near_v5.png", hind, true);
    importLayer("40_HindLeg_Near_v5.png", safety, false);

    importLayer("62_ShoulderFill_ViewL_v5.png", fore, true);
    importLayer("63_UpperArm_ViewL_v5.png", fore, true);
    importLayer("64_Forearm_ViewL_v5.png", fore, true);
    importLayer("65_Paw_ViewL_v5.png", fore, true);
    importLayer("66_ShoulderFill_ViewR_v5.png", fore, true);
    importLayer("67_UpperArm_ViewR_v5.png", fore, true);
    importLayer("68_Forearm_ViewR_v5.png", fore, true);
    importLayer("69_Paw_ViewR_v5.png", fore, true);

    importLayer("60_Foreleg_ViewL_Complete_v5.png", safety, false);
    importLayer("61_Foreleg_ViewR_Complete_v5.png", safety, false);

    importLayer("30_Tail_Complete_v5.png", identity, true);
    importLayer("15_NeckFill_Approved.png", identity, true);
    importLayer("20_Head_Approved.png", identity, true);

    importLayer("micro/70_Iris_L_Clean_v5.png", eyes, true);
    importLayer("micro/71_Pupil_L_v5.png", eyes, true);
    importLayer("micro/72_Highlight_L_v5.png", eyes, true);
    importLayer("micro/73_ClosedLidLine_L_v5.png", eyes, false);
    importLayer("micro/74_EyeWhole_L_Safety_HIDDEN.png", eyes, false);
    importLayer("micro/75_EyeClipMask_L_v5.png", eyes, false);
    importLayer("micro/70_Iris_R_Clean_v5.png", eyes, true);
    importLayer("micro/71_Pupil_R_v5.png", eyes, true);
    importLayer("micro/72_Highlight_R_v5.png", eyes, true);
    importLayer("micro/73_ClosedLidLine_R_v5.png", eyes, false);
    importLayer("micro/74_EyeWhole_R_Safety_HIDDEN.png", eyes, false);
    importLayer("micro/75_EyeClipMask_R_v5.png", eyes, false);

    target.activeLayer = master;
    target.save();
}());
