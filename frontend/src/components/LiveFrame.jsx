function LiveFrame({ imageB64, detection }) {
  return (
    <section>
      <h2>Live Frame</h2>
      {imageB64 ? (
        <img
          src={`data:image/png;base64,${imageB64}`}
          alt="Latest detection frame"
          style={{ maxWidth: '100%', border: '1px solid #ccc' }}
        />
      ) : (
        <p>No frame available.</p>
      )}
      {detection && (
        <p>
          Last detection: <strong>{detection.label}</strong> (
          {typeof detection.confidence === 'number' ? (detection.confidence * 100).toFixed(1) : 'n/a'}%)
        </p>
      )}
    </section>
  );
}

export default LiveFrame;
