export default function AppLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <div>
            <main>{children}</main>
        </div>
    )
}
