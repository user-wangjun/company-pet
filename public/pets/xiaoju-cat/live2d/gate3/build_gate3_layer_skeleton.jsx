#target photoshop

// Gate 3, pass 1: preserve the approved v3 source pixels and build a
// fine-grained, overlapping Live2D material skeleton. This script is
// deliberately conservative: it does not invent hidden anatomy.

(function () {
    if (!app.documents.length) {
        alert("Gate 3: no Photoshop document is open.");
        return;
    }

    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") {
        alert("Gate 3: open xiaoju-planet-login-gate3-working.psd first.");
        return;
    }

    app.displayDialogs = DialogModes.NO;

    function findTopLayer(name) {
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === name || doc.layers[i].name === "SRC_" + name) {
                return doc.layers[i];
            }
        }
        throw new Error("Missing source layer: " + name);
    }

    function unlockTree(container) {
        for (var i = 0; i < container.layers.length; i++) {
            var child = container.layers[i];
            if (child.typename === "LayerSet") unlockTree(child);
            try { child.allLocked = false; } catch (ignored) {}
        }
    }

    function removeOldMaster() {
        for (var i = doc.layerSets.length - 1; i >= 0; i--) {
            if (doc.layerSets[i].name === "GATE3_RIG_PARTS") {
                unlockTree(doc.layerSets[i]);
                doc.layerSets[i].allLocked = false;
                doc.layerSets[i].remove();
            }
        }
    }

    function addGroup(parent, name) {
        var group = parent.layerSets.add();
        group.name = name;
        return group;
    }

    function selectPolygon(points) {
        var region = [];
        for (var i = 0; i < points.length; i++) {
            region.push([UnitValue(points[i][0], "px"), UnitValue(points[i][1], "px")]);
        }
        doc.selection.select(region, SelectionType.REPLACE, 0, false);
    }

    function ellipse(cx, cy, rx, ry, steps) {
        var p = [];
        for (var i = 0; i < steps; i++) {
            var a = Math.PI * 2 * i / steps;
            p.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
        }
        return p;
    }

    function duplicateWhole(source, parent, name) {
        var layer = source.duplicate();
        layer.allLocked = false;
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        layer.visible = true;
        return layer;
    }

    function duplicateSlice(source, parent, name, points) {
        var layer = duplicateWhole(source, parent, name);
        doc.activeLayer = layer;
        selectPolygon(points);
        doc.selection.invert();
        doc.selection.clear();
        doc.selection.deselect();
        return layer;
    }

    function addTodo(parent, name) {
        var layer = doc.artLayers.add();
        layer.name = "TODO_HIDDEN_" + name;
        layer.move(parent, ElementPlacement.INSIDE);
        layer.visible = false;
        return layer;
    }

    removeOldMaster();

    var sources = {
        stars: findTopLayer("Stars_Background"),
        body: findTopLayer("Cat_Body_Base"),
        eyeL: findTopLayer("Eye_L_Whole"),
        eyeR: findTopLayer("Eye_R_Whole"),
        lidL: findTopLayer("Eyelid_L"),
        lidR: findTopLayer("Eyelid_R"),
        armL: findTopLayer("Foreleg_L_Complete"),
        armR: findTopLayer("Foreleg_R_Complete"),
        planet: findTopLayer("Planet_Foreground"),
        shoulderL: findTopLayer("Shoulder_Occluder_L"),
        shoulderR: findTopLayer("Shoulder_Occluder_R")
    };

    var master = doc.layerSets.add();
    master.name = "GATE3_RIG_PARTS";

    // Scene and planet. Planet_Base remains a full transparent planet source;
    // the front rim and highlight are independent overlapping bands.
    var scene = addGroup(master, "01_SCENE_PLANET");
    duplicateWhole(sources.stars, scene, "BG_Stars");
    duplicateWhole(sources.planet, scene, "Planet_Base");
    addTodo(scene, "Planet_BackGlow");
    addTodo(scene, "Planet_SurfaceDetail");

    // Body regions use generous overlapping seams. The overlap is intentional:
    // it gives Cubism deformers room to rotate without exposing cracks.
    var body = addGroup(master, "02_BODY_REAR");
    duplicateSlice(sources.body, body, "Body_Base", [
        [330, 330], [680, 300], [900, 500], [930, 790], [780, 1040],
        [520, 1148], [300, 1080], [255, 820]
    ]);
    duplicateSlice(sources.body, body, "Chest_Fur", [
        [410, 420], [760, 390], [930, 620], [850, 900], [570, 1010], [360, 790]
    ]);
    duplicateSlice(sources.body, body, "RearBody_Base", [
        [210, 620], [520, 560], [690, 800], [610, 1100], [300, 1148], [120, 930]
    ]);
    duplicateSlice(sources.body, body, "Tail_Base", [
        [250, 735], [500, 720], [560, 1015], [355, 1095], [185, 930]
    ]);
    duplicateSlice(sources.body, body, "Tail_Mid", [
        [120, 610], [330, 570], [420, 820], [365, 1040], [165, 965], [80, 790]
    ]);
    duplicateSlice(sources.body, body, "Tail_Tip", [
        [105, 470], [285, 455], [350, 690], [260, 845], [95, 795], [55, 610]
    ]);
    addTodo(body, "Belly_Fill");
    addTodo(body, "Neck_Fill");
    addTodo(body, "Hip_L");
    addTodo(body, "Hip_R");
    addTodo(body, "HindLeg_L");
    addTodo(body, "HindLeg_R");
    addTodo(body, "HindPaw_L");
    addTodo(body, "HindPaw_R");

    var head = addGroup(master, "03_HEAD_FACE_EARS");
    duplicateSlice(sources.body, head, "Head_Base", [
        [360, 35], [1045, 20], [1165, 260], [1140, 600], [950, 780],
        [650, 790], [400, 635], [330, 310]
    ]);
    duplicateSlice(sources.body, head, "Ear_L_Base", [
        [345, 160], [390, 40], [660, 190], [610, 420], [390, 360]
    ]);
    duplicateSlice(sources.body, head, "Ear_R_Base", [
        [820, 175], [1035, 25], [1115, 310], [990, 430], [820, 350]
    ]);
    duplicateSlice(sources.body, head, "Cheek_L", [
        [430, 420], [690, 430], [760, 690], [575, 785], [385, 650]
    ]);
    duplicateSlice(sources.body, head, "Cheek_R", [
        [780, 390], [1080, 360], [1140, 610], [955, 735], [760, 640]
    ]);
    duplicateSlice(sources.body, head, "Muzzle", [
        [655, 520], [970, 500], [1040, 690], [835, 790], [620, 700]
    ]);
    addTodo(head, "Nose");
    addTodo(head, "Mouth_Line");
    addTodo(head, "Mouth_Inside");
    addTodo(head, "Chin_Fur");
    addTodo(head, "Whisker_L");
    addTodo(head, "Whisker_R");

    // Eyes: retain a locked whole-eye underpaint and expose independent pupil
    // and highlight material for gaze prototyping. Gate 3 pass 2 must remove
    // the pupil from the iris underpaint before gaze is declared complete.
    var eyes = addGroup(master, "04_EYES_GAZE");
    duplicateWhole(sources.eyeL, eyes, "Eye_L_Underpaint_LOCKED").allLocked = true;
    duplicateSlice(sources.eyeL, eyes, "Pupil_L", ellipse(708, 549, 30, 36, 32));
    duplicateSlice(sources.eyeL, eyes, "Highlight_L", ellipse(708, 520, 10, 12, 24));
    duplicateWhole(sources.lidL, eyes, "UpperLid_L");
    duplicateWhole(sources.eyeR, eyes, "Eye_R_Underpaint_LOCKED").allLocked = true;
    duplicateSlice(sources.eyeR, eyes, "Pupil_R", ellipse(929, 484, 29, 35, 32));
    duplicateSlice(sources.eyeR, eyes, "Highlight_R", ellipse(927, 456, 10, 12, 24));
    duplicateWhole(sources.lidR, eyes, "UpperLid_R");
    addTodo(eyes, "Iris_L_Clean");
    addTodo(eyes, "Iris_R_Clean");
    addTodo(eyes, "LowerLid_L");
    addTodo(eyes, "LowerLid_R");
    addTodo(eyes, "EyeSocket_Fur_L");
    addTodo(eyes, "EyeSocket_Fur_R");

    function buildArm(source, shoulderCover, parent, side, polys) {
        duplicateSlice(source, parent, "UpperArm_" + side, polys.upper);
        duplicateSlice(source, parent, "Elbow_Fur_" + side, polys.elbow);
        duplicateSlice(source, parent, "Forearm_" + side, polys.forearm);
        duplicateSlice(source, parent, "Wrist_Fur_" + side, polys.wrist);
        duplicateSlice(source, parent, "Paw_" + side, polys.paw);
        duplicateWhole(shoulderCover, parent, "Shoulder_Fill_" + side);
    }

    var arms = addGroup(master, "05_FORELIMBS_JOINTED");
    buildArm(sources.armL, sources.shoulderL, arms, "L", {
        upper: [[400,650],[610,590],[670,780],[610,940],[430,950],[380,790]],
        elbow: [[410,545],[640,510],[690,700],[610,800],[400,715]],
        forearm: [[445,420],[690,390],[715,610],[625,700],[420,585]],
        wrist: [[500,350],[715,330],[730,515],[625,585],[480,485]],
        paw: [[535,320],[725,320],[740,480],[625,535],[515,435]]
    });
    buildArm(sources.armR, sources.shoulderR, arms, "R", {
        upper: [[930,625],[1110,590],[1140,785],[1060,900],[900,820]],
        elbow: [[900,520],[1100,500],[1140,690],[1060,770],[885,670]],
        forearm: [[870,410],[1075,395],[1115,590],[1040,670],[855,555]],
        wrist: [[840,350],[1035,340],[1085,510],[1010,575],[835,470]],
        paw: [[820,325],[1015,325],[1050,475],[965,525],[815,430]]
    });

    // Created last so it is above the jointed forelimbs in Photoshop's stack.
    var foreground = addGroup(master, "06_FOREGROUND_OVERLAY");
    // The complete foreground planet alpha is required here. A narrow rim alone
    // leaves the cover-pose forearms visible below the horizon and creates a
    // floating fragment. Cubism can still warp this full foreground independently.
    duplicateWhole(sources.planet, foreground, "Planet_FrontRim");
    duplicateSlice(sources.planet, foreground, "Planet_Highlight", [
        [290, 1148], [350, 1055], [450, 945], [575, 835], [720, 735],
        [880, 655], [1045, 595], [1210, 535], [1370, 475],
        [1370, 505], [1210, 565], [1045, 625], [885, 685], [725, 765],
        [585, 865], [475, 970], [390, 1080], [330, 1148]
    ]);
    addTodo(foreground, "Planet_ContactShadow");

    // Source layers remain visible so this first-pass PSD is pixel-identical to
    // the approved composition. They are renamed and locked, making the boundary
    // between verified pixels and unfinished hidden reconstruction explicit.
    for (var key in sources) {
        if (sources.hasOwnProperty(key)) {
            var src = sources[key];
            if (src.name.indexOf("SRC_") !== 0) src.name = "SRC_" + src.name;
            src.allLocked = true;
        }
    }

    master.visible = true;
    doc.selection.deselect();
    doc.activeLayer = master;
    doc.save();
    var statusFile = File("D:/CodeWorkspace/电脑桌宠/public/pets/xiaoju-cat/live2d/gate3/gate3-script-status.txt");
    statusFile.open("w");
    statusFile.writeln("OK");
    statusFile.writeln("master=GATE3_RIG_PARTS");
    statusFile.writeln("foreground=06_FOREGROUND_OVERLAY");
    statusFile.writeln("hidden_fill=TODO");
    statusFile.close();
}());
