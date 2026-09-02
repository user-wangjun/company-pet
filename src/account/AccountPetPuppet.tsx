import { useState } from "react";
import { DEFAULT_PET_ID, resolvePetAssetUrl } from "../pet-core/petAssets";
import type { AccountPetMood } from "./accountPetParameters";

const LOGIN_GAZE_ASSET_ROOT = "qa/login-gaze-v8";

const LOGIN_WARM_BACKDROP_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/warm-room-backdrop.png`,
);

const LOGIN_BODY_BASE_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/body-open-base.png`,
);

const LOGIN_LEFT_EYE_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/eye-left-base.png`,
);

const LOGIN_RIGHT_EYE_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/eye-right-base.png`,
);

const LOGIN_LEFT_PUPIL_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/pupil-left.png`,
);

const LOGIN_RIGHT_PUPIL_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/pupil-right.png`,
);

const LOGIN_CLOSED_FACE_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  `${LOGIN_GAZE_ASSET_ROOT}/closed-eye-sockets.png`,
);

export function AccountPetPuppet({
  mood = "idle",
  onPetClick,
}: {
  mood?: AccountPetMood;
  onPetClick?: () => void;
}) {
  const [clickCount, setClickCount] = useState(0);

  const handlePetClick = () => {
    setClickCount((count) => count + 1);
    onPetClick?.();
  };

  return (
    <div
      className="account-warm-pet-scene"
      data-mood={mood}
      data-clicks={clickCount}
      onClick={handlePetClick}
      role="region"
      aria-label="小橘的温馨桌边陪伴场景"
    >
      <img
        className="account-warm-pet-backdrop"
        src={LOGIN_WARM_BACKDROP_URL}
        alt=""
        aria-hidden="true"
        draggable={false}
      />
      <div className="account-warm-pet-shade" aria-hidden="true" />
      <div className="account-layered-pet" aria-hidden="true">
        <img
          className="account-layered-pet-body"
          src={LOGIN_BODY_BASE_URL}
          alt=""
          draggable={false}
        />
        <div className="account-pet-open-eye-layer">
          <div className="account-pet-eye-group">
            <img
              className="account-pet-eye-base account-pet-eye-base-left"
              src={LOGIN_LEFT_EYE_URL}
              alt=""
              draggable={false}
            />
            <img
              className="account-pet-eye-base account-pet-eye-base-right"
              src={LOGIN_RIGHT_EYE_URL}
              alt=""
              draggable={false}
            />
            <img
              className="account-pet-pupil account-pet-pupil-left"
              src={LOGIN_LEFT_PUPIL_URL}
              alt=""
              draggable={false}
            />
            <img
              className="account-pet-pupil account-pet-pupil-right"
              src={LOGIN_RIGHT_PUPIL_URL}
              alt=""
              draggable={false}
            />
          </div>
        </div>
        <div className="account-pet-closed-face-layer" aria-hidden="true">
          <div className="account-pet-lid-group">
            <img
              className="account-pet-closed-face"
              src={LOGIN_CLOSED_FACE_URL}
              alt=""
              draggable={false}
            />
          </div>
        </div>
        <div className="account-pet-password-face-layer" aria-hidden="true">
          <img
            className="account-pet-password-face"
            src={LOGIN_CLOSED_FACE_URL}
            alt=""
            draggable={false}
          />
        </div>
      </div>
    </div>
  );
}
