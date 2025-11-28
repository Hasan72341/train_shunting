function DetectionLog({ events }) {
  return (
    <section>
      <h2>Detection Log</h2>
      {events.length === 0 ? (
        <p>No detections yet.</p>
      ) : (
        <ul>
          {events.map((event, index) => (
            <li key={`${event.label}-${event.timestamp ?? index}`}>
              {event.label} — confidence {event.confidence?.toFixed(2)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default DetectionLog;
