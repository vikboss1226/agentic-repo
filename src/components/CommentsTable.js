import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = 'https://jsonplaceholder.typicode.com/posts/1/comments';

function CommentsTable() {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios
      .get(API_URL)
      .then((response) => {
        setComments(response.data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <p>Loading comments...</p>;
  if (error) return <p>Failed to load comments: {error}</p>;

  return (
    <table border="1" cellPadding="8" style={{ borderCollapse: 'collapse', width: '100%' }}>
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Email</th>
          <th>Comment</th>
        </tr>
      </thead>
      <tbody>
        {comments.map((comment) => (
          <tr key={comment.id}>
            <td>{comment.id}</td>
            <td>{comment.name}</td>
            <td>{comment.email}</td>
            <td>{comment.body}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default CommentsTable;
