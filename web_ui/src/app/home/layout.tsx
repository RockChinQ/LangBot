export default function AppLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <div>
            <h1>sidebar</h1>
            <main>{children}</main>
        </div>
    )
}
